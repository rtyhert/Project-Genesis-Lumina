import asyncio
import logging
from typing import Optional, TypeVar, Callable, Awaitable

log = logging.getLogger("lumina.grpc.retry")

T = TypeVar("T")

DEFAULT_RETRYABLE_CODES = frozenset({
    "UNAVAILABLE", "UNAUTHENTICATED", "RESOURCE_EXHAUSTED",
    "DEADLINE_EXCEEDED", "ABORTED", "INTERNAL", "CANCELLED",
})


class RetryConfig:
    __slots__ = ("max_retries", "base_delay", "max_delay", "backoff_factor", "retryable_codes")

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 5.0,
        backoff_factor: float = 2.0,
        retryable_codes: Optional[frozenset] = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.retryable_codes = retryable_codes or DEFAULT_RETRYABLE_CODES


class GrpcRetryWrapper:
    __slots__ = ("config",)

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()

    async def call(
        self,
        rpc_func: Callable[..., Awaitable[T]],
        *args,
        fallback: Optional[Callable[[], Awaitable[T]]] = None,
        **kwargs,
    ) -> Optional[T]:
        cfg = self.config
        for attempt in range(cfg.max_retries + 1):
            try:
                return await rpc_func(*args, **kwargs)
            except Exception as e:
                grpc_status = getattr(e, "code", None)
                status_name = grpc_status().name if grpc_status else type(e).__name__

                if status_name not in cfg.retryable_codes:
                    log.error(f"Non-retryable RPC error: {e}")
                    return await fallback() if fallback else None

                if attempt < cfg.max_retries:
                    delay = min(cfg.base_delay * (cfg.backoff_factor ** attempt), cfg.max_delay)
                    log.warning(
                        f"RPC failed (attempt {attempt + 1}/{cfg.max_retries + 1}): "
                        f"{status_name}, retrying in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    log.error(f"All retries exhausted: {e}")
                    return await fallback() if fallback else None

        return None


def create_default_wrapper() -> GrpcRetryWrapper:
    return GrpcRetryWrapper(RetryConfig(
        max_retries=3, base_delay=0.5, max_delay=5.0, backoff_factor=2.0,
        retryable_codes=DEFAULT_RETRYABLE_CODES,
    ))
