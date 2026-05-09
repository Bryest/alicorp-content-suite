"""Langfuse observability adapter. Traces + spans pushed to Langfuse Cloud."""

import logging
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from langfuse import Langfuse

from ..config import get_settings

logger = logging.getLogger(__name__)


class Tracer:
    """Facade around the Langfuse client."""

    def __init__(self) -> None:
        self.settings = get_settings()
        if not (self.settings.langfuse_public_key and self.settings.langfuse_secret_key):
            raise RuntimeError(
                "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set. "
                "Configure them in environment variables before starting the API."
            )
        self._client = Langfuse(
            public_key=self.settings.langfuse_public_key,
            secret_key=self.settings.langfuse_secret_key,
            host=self.settings.langfuse_host,
        )
        logger.info("Langfuse: ready")

    @contextmanager
    def trace(self, name: str, *, input_data: Optional[dict] = None) -> Iterator["TraceHandle"]:
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
        try:
            self._client.flush()
        except Exception:  # pragma: no cover
            pass


class TraceHandle:
    def __init__(self, *, real) -> None:
        self._real = real
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
