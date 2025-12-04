# Context Compression Fixes - Implementation Checklist

Use this checklist to track fixes for the issues found in the Context Compression review.

---

## 🔴 Critical Priority (Must Fix Before Production)

### Issue #1: Unbounded Compressed History Growth
**File**: `orchestrator/orchestrator.py` (lines 214-218)

- [ ] Add `MAX_COMPRESSED_TOKENS` constant (25% of max_context_tokens)
- [ ] Implement check in `compress_if_needed()` to detect when compressed history exceeds limit
- [ ] Add re-compression logic when limit exceeded
- [ ] Add test case: `test_compressed_history_does_not_grow_unbounded()`
- [ ] Verify with 100+ message conversation test

**Estimated Time**: 1 day  
**Assignee**: _________

---

### Issue #2: Inaccurate Token Estimation
**Files**: 
- `requirements.txt` (add tiktoken)
- `orchestrator/orchestrator.py` (lines 113-115, 76-78)

- [ ] Add `tiktoken` to requirements.txt
- [ ] Update ContextCompressor.__init__() to initialize tiktoken encoder
- [ ] Replace `_estimate_tokens()` implementation with tiktoken
- [ ] Add fallback to rough estimate if tiktoken fails
- [ ] Update ConversationMessage.__post_init__() token estimation
- [ ] Add test case: `test_token_estimation_accuracy()`
- [ ] Verify token counts match actual model tokenizer

**Estimated Time**: 1 day  
**Assignee**: _________

---

### Issue #3: No Protection Against Compression Failures
**File**: `orchestrator/orchestrator.py` (lines 136-165)

- [ ] Add timeout parameter to `_summarize_chunk()`
- [ ] Implement try-catch around Preprocessor call
- [ ] Add `_extract_key_points()` fallback method
- [ ] Verify summary is actually shorter than original
- [ ] Add retry mechanism (max 2 retries)
- [ ] Emit metrics on compression failures
- [ ] Add test case: `test_summarization_failure_fallback()`
- [ ] Add logging for compression failures

**Estimated Time**: 1 day  
**Assignee**: _________

---

## 🟡 Medium Priority (Should Fix Next Sprint)

### Issue #4: Side Effects in Read Operation
**File**: `orchestrator/orchestrator.py` (lines 225-231)

- [ ] Add `auto_compress` parameter to `get_context()`
- [ ] Update all callers to explicitly call `compress_if_needed()` before `get_context()`
- [ ] Add warning if context near limit and auto_compress=False
- [ ] Update documentation to explain the pattern
- [ ] Add test case: `test_get_context_no_side_effects()`

**Estimated Time**: 0.5 days  
**Assignee**: _________

---

### Issue #5: Race Condition in Compressor Management
**File**: `orchestrator/orchestrator.py` (lines 795-809)

- [ ] Add `_compressor_locks: Dict[str, asyncio.Lock]` to Orchestrator.__init__()
- [ ] Change `get_context_compressor()` to async method
- [ ] Add lock acquisition around compressor creation
- [ ] Update all callers to use `await`
- [ ] Add test case: `test_concurrent_compressor_access()`
- [ ] Verify with concurrent agent execution

**Estimated Time**: 1 day  
**Assignee**: _________

---

## 🟢 Nice to Have (Future Improvements)

### Issue #6: No Compression Effectiveness Metrics
**File**: `orchestrator/orchestrator.py` (lines 246-259)

- [ ] Add `_compressed_message_count` tracking
- [ ] Add `_original_size_before_compression` tracking
- [ ] Update `get_stats()` to include new metrics
- [ ] Add Phoenix/observability integration
- [ ] Create dashboard visualization

**Estimated Time**: 0.5 days  
**Assignee**: _________

---

### Issue #7: Hardcoded Truncation Limits
**Files**: Multiple locations in `orchestrator/orchestrator.py`

- [ ] Add class constants for truncation limits
- [ ] Replace all magic numbers with constants
- [ ] Make configurable via CompressionConfig
- [ ] Update documentation

**Estimated Time**: 0.25 days  
**Assignee**: _________

---

### Issue #8: Missing Compression Event Logging
**File**: `orchestrator/orchestrator.py` (lines 167-223)

- [ ] Add INFO log when compression triggers
- [ ] Log compression statistics (messages compressed, tokens saved)
- [ ] Add DEBUG logs for chunk processing
- [ ] Emit Phoenix traces for compression events
- [ ] Add compression duration tracking

**Estimated Time**: 0.25 days  
**Assignee**: _________

---

### Issue #9: Config Schema Inconsistency
**Files**: 
- `orchestrator/config_schema.py` (MakerConfig class)
- `orchestrator/orchestrator.py` (line 451)

- [ ] Add `summary_chunk_size` field to MakerConfig in config_schema.py
- [ ] Update orchestrator initialization to use config value
- [ ] Remove "Not in config schema yet" comment
- [ ] Update .maker.json.example
- [ ] Update documentation

**Estimated Time**: 0.25 days  
**Assignee**: _________

---

## Testing Checklist

### Unit Tests (create `tests/test_context_compression.py`)

- [ ] `test_compression_triggers_at_threshold()` - Verify 95% threshold works
- [ ] `test_compressed_history_does_not_grow_unbounded()` - Issue #1
- [ ] `test_token_estimation_accuracy()` - Issue #2
- [ ] `test_summarization_failure_fallback()` - Issue #3
- [ ] `test_get_context_no_side_effects()` - Issue #4
- [ ] `test_concurrent_compressor_access()` - Issue #5
- [ ] `test_compression_saves_tokens()` - Verify compression works
- [ ] `test_recent_messages_preserved()` - Verify recent window
- [ ] `test_custom_compact_instructions()` - Verify custom instructions work

### Integration Tests

- [ ] Test with 100+ message conversation
- [ ] Test with multi-agent concurrent access
- [ ] Test with Preprocessor failures
- [ ] Test with various content types (code, prose, mixed)
- [ ] Test compression with long-running task (1000+ messages)

### Performance Tests

- [ ] Measure compression time for various message counts
- [ ] Verify compression is non-blocking
- [ ] Test memory usage during compression
- [ ] Verify no memory leaks in long conversations

---

## Definition of Done

- [ ] All critical (🔴) issues fixed and tested
- [ ] All medium (🟡) issues fixed and tested
- [ ] Unit test coverage > 90% for ContextCompressor
- [ ] Integration tests pass with 100+ message conversations
- [ ] No memory leaks detected in 1000+ message test
- [ ] Performance meets requirements (compression < 5s for 100 messages)
- [ ] Documentation updated
- [ ] Code reviewed and approved
- [ ] Phoenix observability integration complete
- [ ] Deployed to staging and verified

---

## Progress Tracking

**Started**: _________  
**Target Completion**: _________ (estimated 5 days for critical + medium)  
**Actual Completion**: _________

**Status Updates**:

- [ ] Day 1: _________
- [ ] Day 2: _________
- [ ] Day 3: _________
- [ ] Day 4: _________
- [ ] Day 5: _________

---

## Notes

Use this section for tracking blockers, decisions, or important observations during implementation.

---

**Last Updated**: December 4, 2025  
**Review Document**: See `CONTEXT_COMPRESSION_REVIEW.md` for detailed analysis
