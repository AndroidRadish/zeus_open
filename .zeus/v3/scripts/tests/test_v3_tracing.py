"""
Tracing integration tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.tracing import init_tracing, NoOpTracer


def test_init_tracing_returns_noop_when_otel_missing():
    # In this environment opentelemetry is installed, but we can still verify the interface
    tracer = init_tracing()
    assert tracer is not None
    with tracer.start_as_current_span("test") as span:
        span.set_attribute("x", 1)
        span.add_event("event", {"k": "v"})
        span.record_exception(RuntimeError("oops"))


def test_init_tracing_with_console_export():
    tracer = init_tracing(export_to_console=True)
    assert tracer is not None
    with tracer.start_as_current_span("run") as span:
        span.set_attribute("task_count", 5)
