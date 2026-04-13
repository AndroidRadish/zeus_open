"""
OpenTelemetry tracing support for ZeusOpen v3.

Lightweight wrapper that initializes a tracer if opentelemetry is available.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    _OTEL_AVAILABLE = True
except Exception:  # pragma: no cover
    _OTEL_AVAILABLE = False


class NoOpTracer:
    """Fallback tracer when opentelemetry is not installed."""

    @contextmanager
    def start_as_current_span(self, name: str, **kwargs: Any) -> Generator[Any, None, None]:
        yield NoOpSpan()


class NoOpSpan:
    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        pass

    def record_exception(self, exception: BaseException) -> None:
        pass


_NOOP = NoOpTracer()
_provider_set = False


def init_tracing(service_name: str = "zeus-open-v3", export_to_console: bool = False) -> trace.Tracer | NoOpTracer:
    """Initialize the global tracer provider and return a tracer."""
    global _provider_set
    if not _OTEL_AVAILABLE:
        return _NOOP
    if not _provider_set:
        provider = TracerProvider()
        if export_to_console:
            processor = BatchSpanProcessor(ConsoleSpanExporter())
            provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        _provider_set = True
    return trace.get_tracer(service_name)
