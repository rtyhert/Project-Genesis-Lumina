import pytest
from grpc_retry import GrpcRetryWrapper, RetryConfig


class FakeGrpcError(Exception):
    def __init__(self, code_name: str):
        self._code_name = code_name
        super().__init__(code_name)

    def code(self):
        class FakeCode:
            name = self._code_name
        return FakeCode()


class TestGrpcRetryWrapper:
    @pytest.mark.asyncio
    async def test_success_first_attempt(self):
        wrapper = GrpcRetryWrapper(RetryConfig(max_retries=2))

        async def ok():
            return "ok"

        result = await wrapper.call(ok)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        wrapper = GrpcRetryWrapper(RetryConfig(max_retries=3, base_delay=0.01))

        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise FakeGrpcError("UNAVAILABLE")
            return "ok"

        result = await wrapper.call(flaky)
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retries_exhausted_returns_none(self):
        wrapper = GrpcRetryWrapper(RetryConfig(max_retries=2, base_delay=0.01))

        async def always_fails():
            raise FakeGrpcError("UNAVAILABLE")

        result = await wrapper.call(always_fails)
        assert result is None

    @pytest.mark.asyncio
    async def test_fallback_on_exhaustion(self):
        wrapper = GrpcRetryWrapper(RetryConfig(max_retries=1, base_delay=0.01))

        async def always_fails():
            raise FakeGrpcError("UNAVAILABLE")

        async def fallback():
            return "fallback"

        result = await wrapper.call(always_fails, fallback=fallback)
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_non_retryable_error(self):
        wrapper = GrpcRetryWrapper(RetryConfig(max_retries=3, base_delay=0.01))

        async def fails():
            raise FakeGrpcError("INVALID_ARGUMENT")

        result = await wrapper.call(fails)
        assert result is None

    @pytest.mark.asyncio
    async def test_non_retryable_with_fallback(self):
        wrapper = GrpcRetryWrapper(RetryConfig(max_retries=3, base_delay=0.01))

        async def fails():
            raise FakeGrpcError("INVALID_ARGUMENT")

        async def fallback():
            return "fallback"

        result = await wrapper.call(fails, fallback=fallback)
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_plain_exception_treated_as_non_retryable(self):
        wrapper = GrpcRetryWrapper(RetryConfig(max_retries=2, base_delay=0.01))

        async def fails():
            raise ValueError("plain error")

        result = await wrapper.call(fails)
        assert result is None

    @pytest.mark.asyncio
    async def test_retryable_codes_config(self):
        cfg = RetryConfig(max_retries=1, base_delay=0.01, retryable_codes=frozenset({"CUSTOM_ERROR"}))
        wrapper = GrpcRetryWrapper(cfg)

        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            raise FakeGrpcError("CUSTOM_ERROR")

        result = await wrapper.call(flaky)
        assert result is None
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_plain_exception_with_fallback(self):
        wrapper = GrpcRetryWrapper(RetryConfig(max_retries=2, base_delay=0.01))

        async def fails():
            raise ValueError("plain error")

        async def fallback():
            return "fallback"

        result = await wrapper.call(fails, fallback=fallback)
        assert result == "fallback"

    def test_create_default_wrapper(self):
        from grpc_retry import create_default_wrapper
        wrapper = create_default_wrapper()
        assert wrapper.config.max_retries == 3
        assert wrapper.config.base_delay == 0.5
