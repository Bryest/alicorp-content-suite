"""
Langfuse observability adapter.

REAL mode: pushes spans + traces to Langfuse Cloud.
MOCK mode: writes structured trace records to stdout/logger so evaluators
can still see retrieval/prompt/latency in the console.

We expose a unified `Tracer` context manager so the application services
look the same in both modes.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from ..config import get_settings

logger = logging.getLogger("langfuse-mock")


class _MockTrace:
    """Stand-in trace object — collects spans and prints on close."""

    def __init__(self, name: str, input_data: Optional[dict] = None):
        self.id = str(uuid.uuid4())
        self.name = name
        self.input = input_data or {}
        self.output: dict[str, Any] = {}
        self.spans: list[dict[str, Any]] = []
        self.started_at = time.time()

    def add_span(self, span: dict[str, Any]) -> None:
        self.spans.append(span)

    def finish(self, output: Optional[dict] = None) -> None:
        self.output = output or {}
        elapsed_ms = int((time.time() - self.started_at) * 1000)
        payload = {
            "trace_id": self.id,
            "trace": self.name,
            "elapsed_ms": elapsed_ms,
            "input": self.input,
            "output": self.output,
            "spans": self.spans,
        }
        logger.info("LANGFUSE-MOCK TRACE %s", json.dumps(payload, default=str)[:2000])


class Tracer:
    """
    Tracer facade.

    In real mode wraps a Langfuse client; in mock mode wraps `_MockTrace`.
    The application layer uses `Tracer.trace(name, input)` as a context
    manager and `tracer.span(name, input, output, ms)` to log child spans.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None
        if not self.settings.langfuse_mocked:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=self.settings.langfuse_public_key,
                    secret_key=self.settings.langfuse_secret_key,
                    host=self.settings.langfuse_host,
                )
                logger.info("Langfuse: REAL mode")
            except Exception as e:  # pragma: no cover
                logger.warning(f"Langfuse init failed: {e}. Falling back to mock.")
                self._client = None
        if self._client is None:
            logger.info("Langfuse: MOCK mode (stdout traces)")

    @property
    def is_mocked(self) -> bool:
        return self._client is None

    @contextmanager
    def trace(self, name: str, *, input_data: Optional[dict] = None) -> Iterator["TraceHandle"]:
        if self._client is None:
            mock = _MockTrace(name, input_data)
            handle = TraceHandle(mock=mock)
            try:
                yield handle
            finally:
                mock.finish(handle.output)
            return

        # Real mode
        trace = self._client.trace(name=name, input=input_data or {})
        handle = TraceHandle(real=trace)
        try:
            yield handle
        finally:
            try:
                trace.update(output=handle.output)
                self._client.flush()
            except Exception as e:  # pragma: no cover
                logger.warning(f"Langfuse flush failed: {e}")

    def flush(self) -> None:
        if self._client is not None:
            try:
                self._client.flush()
            except Exception:  # pragma: no cover
                pass


class TraceHandle:
    def __init__(self, *, real=None, mock: Optional[_MockTrace] = None):
        self._real = real
        self._mock = mock
        self.output: dict[str, Any] = {}

    def span(
        self,
        name: str,
        *,
        input_data: Optional[dict] = None,
        output_data: Optional[dict] = None,
        latency_ms: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        rec = {
            "name": name,
            "input": input_data or {},
            "output": output_data or {},
            "latency_ms": latency_ms,
            "metadata": metadata or {},
        }
        if self._mock is not None:
            self._mock.add_span(rec)
            return
        if self._real is not None:
            try:
                self._real.span(
                    name=name,
                    input=input_data or {},
                    output=output_data or {},
                    metadata={"latency_ms": latency_ms, **(metadata or {})},
                )
            except Exception as e:  # pragma: no cover
                logger.warning(f"Langfuse span emit failed: {e}")

    def set_output(self, output: dict[str, Any]) -> None:
        self.output = output


_tracer: Optional[Tracer] = None


def get_tracer() -> Tracer:
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer
