# Context Compression (ContextCompressor) Review

**Date**: December 4, 2025  
**Reviewer**: Background Agent  
**Component**: `orchestrator/orchestrator.py` - `ContextCompressor` class (lines 81-306)

## Executive Summary

The `ContextCompressor` class implements hierarchical context compression with a sliding window approach (similar to Claude's method). While the overall architecture is sound, there are **5 critical issues** and **3 minor issues** that could cause problems in production, especially during long conversations or high-throughput scenarios.

---

## Critical Issues

### 1. **Unbounded Compressed History Growth** ⚠️ HIGH PRIORITY

**Location**: Lines 214-218

**Problem**: 
```python
new_compressed = "\n---\n".join(summaries)
if self.compressed_history:
    self.compressed_history = f"{self.compressed_history}\n---\n{new_compressed}"
else:
    self.compressed_history = new_compressed
```

The compressed history continuously accumulates without ever being re-compressed. In a long-running conversation:
- Iteration 1: Compress 10 messages → 2KB compressed
- Iteration 2: Compress 10 more messages → Add 2KB → Total 4KB
- Iteration 100: Total compressed history could be 200KB+

**Impact**: 
- The compressed history can eventually exceed `max_context_tokens` itself
- No mechanism exists to re-compress the compressed history
- Long conversations will hit context limits even with compression enabled

**Recommendation**:
```python
# Option 1: Set a maximum compressed history size
MAX_COMPRESSED_TOKENS = self.max_context_tokens // 4  # 25% of total budget

# When compressed_history exceeds limit, re-summarize it
if self.compressed_token_count > MAX_COMPRESSED_TOKENS:
    # Re-compress the entire compressed history
    self.compressed_history = await self._summarize_chunk([
        ConversationMessage(role="system", content=self.compressed_history)
    ])
    self.compressed_token_count = self._estimate_tokens(self.compressed_history)

# Option 2: Use a ring buffer approach - discard oldest compressed chunks
# when limit is reached (FIFO)
```

---

### 2. **Inaccurate Token Estimation** ⚠️ HIGH PRIORITY

**Location**: Lines 113-115, 76-78

**Problem**:
```python
def _estimate_tokens(self, text: str) -> int:
    """Rough token estimate (4 chars per token)"""
    return len(text) // 4
```

This is extremely inaccurate:
- GPT tokenizers average ~4 chars/token for English prose
- Code can be 2-3 chars/token (lots of symbols, short tokens)
- Asian languages can be 1-2 chars/token
- The estimate can be off by 50-200%

**Impact**:
- Compression might trigger too early or too late
- Context might actually exceed model limits even though estimate says it's safe
- The 95% threshold could actually be 150% or 50% in reality

**Recommendation**:
```python
# Use tiktoken for accurate token counting
import tiktoken

def __init__(self, ...):
    # Initialize tokenizer (cache it)
    try:
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
    except:
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

def _estimate_tokens(self, text: str) -> int:
    """Accurate token count using tiktoken"""
    try:
        return len(self.tokenizer.encode(text))
    except Exception as e:
        # Fallback to rough estimate if tokenizer fails
        logger.warning(f"Token estimation failed: {e}, using fallback")
        return len(text) // 4
```

---

### 3. **Potential Side Effects in Read Operation** ⚠️ MEDIUM PRIORITY

**Location**: Lines 225-231

**Problem**:
```python
async def get_context(self, include_system: bool = True) -> str:
    """Get the full context string for sending to an agent."""
    # Proactive compression: Check and compress if needed before returning context
    await self.compress_if_needed()
    # ... returns context
```

A read operation (`get_context()`) can mutate state by triggering compression. This violates the principle of least surprise and could cause issues:
- Debugging becomes harder (reading state changes state)
- Race conditions if multiple agents call `get_context()` simultaneously
- Unexpected behavior in testing scenarios

**Impact**:
- Difficult to debug compression issues
- Potential race conditions in concurrent scenarios
- Violates functional programming principles (side effects in getters)

**Recommendation**:
```python
# Option 1: Separate read from compression
async def get_context(self, include_system: bool = True, 
                     auto_compress: bool = True) -> str:
    """Get the full context string for sending to an agent.
    
    Args:
        auto_compress: If True, compress if needed before returning.
                      Set to False if you want to control compression separately.
    """
    if auto_compress:
        await self.compress_if_needed()
    # ... build and return context

# Option 2: Explicit compression with warnings
async def get_context(self, include_system: bool = True) -> str:
    """Get context without side effects. Call compress_if_needed() first."""
    total_tokens = self._calculate_total_tokens()
    if total_tokens > self.max_context_tokens * 0.95:
        logger.warning(
            f"Context near limit ({total_tokens}/{self.max_context_tokens}). "
            "Call compress_if_needed() before get_context()."
        )
    # ... build and return context
```

---

### 4. **No Protection Against Compression Failures** ⚠️ MEDIUM PRIORITY

**Location**: Lines 136-165

**Problem**:
```python
summary = await self.orchestrator.call_agent_sync(
    AgentName.PREPROCESSOR,
    summary_prompt,
    f"Conversation to summarize:\n{chunk_text}",
    temperature=0.1
)
return summary if not summary.startswith("Error:") else chunk_text[:500]
```

If the Preprocessor agent fails or returns an error:
- Fallback is to return `chunk_text[:500]`
- This truncation might still be larger than intended
- If the chunk was 10KB, truncating to 500 chars doesn't help much
- No retry mechanism or circuit breaker

**Impact**:
- Compression could silently fail, causing context overflow
- Truncated fallback might lose critical information
- No visibility into compression failures

**Recommendation**:
```python
async def _summarize_chunk(self, messages: List[ConversationMessage]) -> str:
    """Use Preprocessor (Gemma2-2B) to summarize a chunk of messages"""
    if not messages:
        return ""
    
    chunk_text = "\n".join([
        f"{msg.role}: {msg.content[:1000]}" for msg in messages
    ])
    
    # Build prompt...
    
    try:
        summary = await self.orchestrator.call_agent_sync(
            AgentName.PREPROCESSOR,
            summary_prompt,
            f"Conversation to summarize:\n{chunk_text}",
            temperature=0.1,
            timeout=30  # Add timeout
        )
        
        if summary.startswith("Error:"):
            logger.error(f"Preprocessor returned error during summarization: {summary}")
            # Use better fallback - extract key information
            return self._extract_key_points(messages)
        
        # Verify summary is actually shorter
        if len(summary) >= len(chunk_text):
            logger.warning("Summary is not shorter than original, using extraction")
            return self._extract_key_points(messages)
        
        return summary
        
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        # Emit metric for monitoring
        self.orchestrator.metrics.increment("compression_failures")
        return self._extract_key_points(messages)

def _extract_key_points(self, messages: List[ConversationMessage]) -> str:
    """Fallback: Extract key points without LLM"""
    # Extract last message + any code blocks + file references
    key_info = []
    for msg in messages[-3:]:  # Last 3 messages
        content = msg.content[:200]  # First 200 chars
        if "```" in msg.content or "file:" in msg.content:
            key_info.append(f"{msg.role}: {content}...")
    return "\n".join(key_info) or "Previous discussion omitted due to compression failure"
```

---

### 5. **Race Condition in Task Compressor Management** ⚠️ MEDIUM PRIORITY

**Location**: Lines 795-809

**Problem**:
```python
def get_context_compressor(self, task_id: str) -> ContextCompressor:
    """Get or create a context compressor for a task"""
    if task_id not in self._context_compressors:
        self._context_compressors[task_id] = ContextCompressor(...)
    return self._context_compressors[task_id]
```

This is not thread-safe. If multiple agents access the same task simultaneously:
- Race condition between checking existence and creating compressor
- Could create multiple compressors for same task_id
- No locking mechanism

**Impact**:
- In concurrent scenarios, compression state could be inconsistent
- Multiple compressors could exist for same task, causing memory leaks
- Compression statistics would be inaccurate

**Recommendation**:
```python
import asyncio
from collections import defaultdict

def __init__(self, ...):
    self._context_compressors: Dict[str, ContextCompressor] = {}
    self._compressor_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

async def get_context_compressor(self, task_id: str) -> ContextCompressor:
    """Get or create a context compressor for a task (thread-safe)"""
    async with self._compressor_locks[task_id]:
        if task_id not in self._context_compressors:
            self._context_compressors[task_id] = ContextCompressor(
                orchestrator=self,
                max_context_tokens=self.max_context_tokens,
                recent_window_tokens=self.recent_window_tokens,
                summary_chunk_size=self.summary_chunk_size
            )
        return self._context_compressors[task_id]
```

---

## Minor Issues

### 6. **No Compression Effectiveness Metrics** ℹ️ LOW PRIORITY

**Problem**: No way to track if compression is actually helping:
- How much space was saved?
- How often does compression trigger?
- Are summaries actually shorter?

**Recommendation**:
```python
def get_stats(self) -> Dict[str, Any]:
    """Get compression statistics"""
    recent_tokens = sum(m.token_estimate for m in self.conversation_history)
    total = recent_tokens + self.compressed_token_count
    
    # Calculate how many messages were compressed
    compressed_message_count = getattr(self, '_compressed_message_count', 0)
    original_size_before_compression = getattr(self, '_original_size_before_compression', 0)
    
    return {
        "session_id": self.session_id,
        "total_messages": len(self.conversation_history),
        "recent_tokens": recent_tokens,
        "compressed_tokens": self.compressed_token_count,
        "total_tokens": total,
        "max_tokens": self.max_context_tokens,
        "used_percent": round((total / self.max_context_tokens) * 100, 1),
        "compression_ratio": round(self.compressed_token_count / max(1, total), 3),
        # New metrics
        "compressed_message_count": compressed_message_count,
        "compression_savings": original_size_before_compression - self.compressed_token_count,
        "compression_efficiency": round(
            (original_size_before_compression - self.compressed_token_count) / 
            max(1, original_size_before_compression), 3
        )
    }
```

---

### 7. **Hardcoded Truncation Limits** ℹ️ LOW PRIORITY

**Location**: Lines 142, 2298, 2335, 2750, 2780

**Problem**: Magic numbers for truncation:
```python
f"{msg.role}: {msg.content[:1000]}" for msg in messages
compressor.add_message("assistant", f"Generated code:\n{code_output[:2000]}")
compressor.add_message("reviewer", review_output[:1000])
```

These should be configurable constants.

**Recommendation**:
```python
class ContextCompressor:
    # Class constants
    MAX_MESSAGE_PREVIEW_LENGTH = 1000
    MAX_CODE_PREVIEW_LENGTH = 2000
    MAX_REVIEW_PREVIEW_LENGTH = 1000
    
    # Use them consistently
    chunk_text = "\n".join([
        f"{msg.role}: {msg.content[:self.MAX_MESSAGE_PREVIEW_LENGTH]}" 
        for msg in messages
    ])
```

---

### 8. **Missing Compression Event Logging** ℹ️ LOW PRIORITY

**Problem**: Compression happens silently. For debugging and monitoring, we need visibility.

**Recommendation**:
```python
async def compress_if_needed(self, force: bool = False) -> bool:
    # ... existing code ...
    
    if not older:
        return False
    
    # Log compression event
    logger.info(
        f"Compression triggered for session {self.session_id}: "
        f"{len(older)} messages ({sum(m.token_estimate for m in older)} tokens) "
        f"→ compressing into {len(chunks)} chunks"
    )
    
    # ... perform compression ...
    
    compression_saved = sum(m.token_estimate for m in older) - len(new_compressed) // 4
    logger.info(
        f"Compression complete: saved {compression_saved} tokens "
        f"({len(older)} messages → {len(new_compressed)} chars)"
    )
    
    # Emit metrics for Phoenix/observability
    if hasattr(self.orchestrator, 'metrics'):
        self.orchestrator.metrics.record_compression(
            session_id=self.session_id,
            messages_compressed=len(older),
            tokens_saved=compression_saved
        )
    
    return True
```

---

## Testing Gaps

**No dedicated tests found** for the `ContextCompressor` class. Recommended test scenarios:

1. **Test compression trigger at 95% threshold**
```python
async def test_compression_triggers_at_threshold():
    orchestrator = MockOrchestrator()
    compressor = ContextCompressor(orchestrator, max_context_tokens=1000, recent_window_tokens=200)
    
    # Add messages until we hit 95% (950 tokens = 3800 chars)
    for i in range(20):
        compressor.add_message("user", "x" * 190)  # ~190 chars = ~47 tokens each
    
    # Should trigger compression
    compressed = await compressor.compress_if_needed()
    assert compressed == True
    assert compressor.compressed_token_count > 0
```

2. **Test compressed history accumulation**
```python
async def test_compressed_history_does_not_grow_unbounded():
    """Test that compressed history has a maximum size"""
    # This test will FAIL with current implementation
    compressor = ContextCompressor(orchestrator, max_context_tokens=10000)
    
    # Simulate 100 compression cycles
    for cycle in range(100):
        for i in range(10):
            compressor.add_message("user", "x" * 200)
        await compressor.compress_if_needed(force=True)
    
    # Compressed history should not exceed 25% of max_context_tokens
    assert compressor.compressed_token_count < compressor.max_context_tokens * 0.25
```

3. **Test summarization failure handling**
```python
async def test_summarization_failure_fallback():
    """Test that compression handles Preprocessor failures gracefully"""
    orchestrator = FailingMockOrchestrator()  # Returns "Error: ..." always
    compressor = ContextCompressor(orchestrator, max_context_tokens=1000)
    
    for i in range(50):
        compressor.add_message("user", "x" * 100)
    
    # Should not raise exception
    await compressor.compress_if_needed(force=True)
    
    # Should have some compressed history (fallback extraction)
    assert compressor.compressed_history != ""
```

4. **Test concurrent access**
```python
async def test_concurrent_compressor_access():
    """Test that multiple agents can safely access compressor"""
    orchestrator = MockOrchestrator()
    
    async def add_messages(task_id):
        compressor = await orchestrator.get_context_compressor(task_id)
        for i in range(10):
            compressor.add_message("user", f"Message {i}")
            await compressor.compress_if_needed()
    
    # Run 10 agents concurrently on same task
    await asyncio.gather(*[add_messages("task-1") for _ in range(10)])
    
    # Should only have one compressor instance
    assert len(orchestrator._context_compressors) == 1
```

---

## Performance Considerations

### Current Performance Issues:

1. **Blocking summarization**: `_summarize_chunk()` calls Preprocessor synchronously per chunk
   - For 10 chunks, this is 10 sequential LLM calls
   - Current implementation uses `asyncio.gather()` which helps, but still blocks during compression

2. **No compression caching**: If same content appears multiple times, it's re-summarized

3. **Token estimation overhead**: Calculating token estimates on every message add

### Optimization Recommendations:

```python
# 1. Add compression result caching
from functools import lru_cache
import hashlib

def _cache_key(self, messages: List[ConversationMessage]) -> str:
    """Generate cache key for messages"""
    content = "".join(m.content for m in messages)
    return hashlib.md5(content.encode()).hexdigest()

@lru_cache(maxsize=128)
async def _summarize_chunk_cached(self, cache_key: str, chunk_text: str) -> str:
    """Cached summarization"""
    return await self._summarize_chunk_impl(chunk_text)

# 2. Add compression in background (don't block on compression)
async def compress_in_background(self):
    """Trigger compression in background without blocking"""
    asyncio.create_task(self.compress_if_needed())

# 3. Batch token estimation
def _batch_estimate_tokens(self, texts: List[str]) -> List[int]:
    """Estimate tokens for multiple texts efficiently"""
    if hasattr(self, 'tokenizer'):
        # Batch encode is faster than individual encodes
        return [len(tokens) for tokens in self.tokenizer.encode_batch(texts)]
    else:
        return [len(text) // 4 for text in texts]
```

---

## Configuration Issues

### Missing Config Schema Entry

**Location**: `orchestrator/config_schema.py` (MakerConfig class)

**Problem**: `SUMMARY_CHUNK_SIZE` is missing from the config schema but is used throughout the codebase.

```python
# In orchestrator/orchestrator.py line 451
self.summary_chunk_size = int(os.getenv("SUMMARY_CHUNK_SIZE", "4000"))  # Not in config schema yet
```

This means:
- Cannot be configured via `.maker.json` file
- Only available as environment variable
- Inconsistent with other compression settings (`max_context_tokens` and `recent_window_tokens` ARE in schema)

**Fix**:
```python
# In orchestrator/config_schema.py, add to MakerConfig class:
class MakerConfig(BaseModel):
    # ... existing fields ...
    recent_window_tokens: int = Field(
        default=8000,
        ge=1000,
        description="Recent window size in tokens (kept in full)"
    )
    summary_chunk_size: int = Field(  # ADD THIS
        default=4000,
        ge=500,
        description="Chunk size for summarization in tokens"
    )
```

Then update `orchestrator/orchestrator.py` line 451:
```python
# Remove the comment about "Not in config schema yet"
self.summary_chunk_size = self.config.maker.summary_chunk_size
```

---

### Proposed Unified Configuration

Current configuration is hardcoded in several places. Should be centralized:

```python
@dataclass
class CompressionConfig:
    """Configuration for context compression"""
    max_context_tokens: int = 32000
    recent_window_tokens: int = 8000
    summary_chunk_size: int = 4000
    compression_trigger_threshold: float = 0.95  # 95%
    max_compressed_history_ratio: float = 0.25  # 25% of max
    enable_compression_cache: bool = True
    compression_cache_size: int = 128
    summarization_timeout: int = 30  # seconds
    token_estimation_method: str = "tiktoken"  # or "rough"

class ContextCompressor:
    def __init__(self, orchestrator: 'Orchestrator', 
                 config: Optional[CompressionConfig] = None):
        self.config = config or CompressionConfig()
        # Use self.config throughout...
```

---

## Priority Recommendations

### 🔴 Must Fix (Before Production):
1. **Issue #1**: Implement compressed history size limits (unbounded growth)
2. **Issue #2**: Replace token estimation with tiktoken
3. **Issue #4**: Add robust error handling for summarization failures

### 🟡 Should Fix (Next Sprint):
4. **Issue #3**: Remove side effects from `get_context()` 
5. **Issue #5**: Add thread-safe compressor management
6. **Testing**: Add comprehensive test coverage

### 🟢 Nice to Have (Future):
7. **Issue #6**: Add compression effectiveness metrics
8. **Issue #7-8**: Improve logging and configuration
9. **Performance**: Add caching and background compression

---

## Summary

The `ContextCompressor` implementation is a solid foundation but has several critical issues that could cause problems in production:

1. **Compressed history can grow unbounded** - most critical issue
2. **Token estimation is highly inaccurate** - could cause context overflows
3. **No protection against summarization failures** - silent failures possible
4. **Side effects in read operations** - violates functional principles
5. **Missing thread-safety** - potential race conditions

**Estimated effort to fix critical issues**: 2-3 days
**Risk of not fixing**: HIGH - long conversations will fail, context limits will be exceeded

**Recommended next steps**:
1. Add unit tests for compression behavior
2. Implement compressed history size limits
3. Switch to tiktoken for accurate token counting
4. Add comprehensive error handling
5. Add metrics and monitoring for compression effectiveness
