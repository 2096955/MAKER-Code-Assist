#!/usr/bin/env python3
"""
Phoenix observability integration
OpenTelemetry tracing for all agent interactions
"""

import os
from functools import wraps
from typing import Optional, Callable, Any
import traceback

# Try to import OpenTelemetry (optional dependency)
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    # Create dummy classes for when OpenTelemetry is not available
    class trace:
        @staticmethod
        def get_tracer(name):
            return DummyTracer()
    
    class DummyTracer:
        def start_as_current_span(self, name):
            return DummySpan()
    
    class DummySpan:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def set_attribute(self, *args, **kwargs):
            pass
        def record_exception(self, *args, **kwargs):
            pass

# Configure Phoenix endpoint
PHOENIX_ENDPOINT = os.getenv("PHOENIX_ENDPOINT", "http://localhost:6006/v1/traces")
PHOENIX_ENABLED = os.getenv("PHOENIX_ENABLED", "true").lower() == "true"

_tracer = None

def setup_phoenix_tracing():
    """Initialize OpenTelemetry tracing to Phoenix"""
    global _tracer
    
    if not OPENTELEMETRY_AVAILABLE:
        print("[Phoenix] OpenTelemetry not installed. Install with: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http")
        _tracer = DummyTracer()
        return _tracer
    
    if not PHOENIX_ENABLED:
        print("[Phoenix] Observability disabled (PHOENIX_ENABLED=false)")
        _tracer = DummyTracer()
        return _tracer
    
    try:
        resource = Resource.create({
            "service.name": "maker-orchestrator",
            "service.version": "1.0.0",
        })
        
        provider = TracerProvider(resource=resource)
        
        # Export to Phoenix
        otlp_exporter = OTLPSpanExporter(
            endpoint=PHOENIX_ENDPOINT,
            headers={}
        )
        
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(provider)
        
        _tracer = trace.get_tracer(__name__)
        print(f"[Phoenix] Observability enabled, sending traces to {PHOENIX_ENDPOINT}")
        return _tracer
    except Exception as e:
        print(f"[Phoenix] Failed to initialize: {e}")
        _tracer = DummyTracer()
        return _tracer

def get_tracer():
    """Get the global tracer instance"""
    global _tracer
    if _tracer is None:
        _tracer = setup_phoenix_tracing()
    return _tracer

def trace_agent_call(agent_name: str, model: str = "default"):
    """Decorator for tracing agent calls"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(f"agent.{agent_name}") as span:
                span.set_attribute("agent.name", agent_name)
                span.set_attribute("model", model)
                span.set_attribute("maker.k_value", os.getenv("MAKER_VOTE_K", "3"))
                
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("agent.success", True)
                    if isinstance(result, str):
                        span.set_attribute("agent.response_length", len(result))
                    return result
                except Exception as e:
                    span.set_attribute("agent.success", False)
                    span.set_attribute("agent.error", str(e))
                    if hasattr(span, 'record_exception'):
                        span.record_exception(e)
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(f"agent.{agent_name}") as span:
                span.set_attribute("agent.name", agent_name)
                span.set_attribute("model", model)
                span.set_attribute("maker.k_value", os.getenv("MAKER_VOTE_K", "3"))
                
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("agent.success", True)
                    if isinstance(result, str):
                        span.set_attribute("agent.response_length", len(result))
                    return result
                except Exception as e:
                    span.set_attribute("agent.success", False)
                    span.set_attribute("agent.error", str(e))
                    if hasattr(span, 'record_exception'):
                        span.record_exception(e)
                    raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator

def trace_maker_voting(candidates: list, k: int):
    """Trace MAKER voting process
    
    Returns a context manager that must be entered with 'with'.
    Set attributes inside the context.
    """
    tracer = get_tracer()
    return tracer.start_as_current_span("maker.voting")

def trace_memory_query(query: str, compression_ratio: float):
    """Trace memory query"""
    tracer = get_tracer()
    span = tracer.start_as_current_span("memory.query")
    span.set_attribute("memory.query_length", len(query))
    span.set_attribute("memory.compression_ratio", compression_ratio)
    return span

# Initialize on import
if OPENTELEMETRY_AVAILABLE and PHOENIX_ENABLED:
    setup_phoenix_tracing()

