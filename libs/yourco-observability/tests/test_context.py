from yourco_observability import BoundContext, current_context, set_current_context
from yourco_observability.context import reset_current_context


def test_no_context_by_default() -> None:
    assert current_context() is None


def test_set_and_reset_context() -> None:
    ctx = BoundContext(request_id="req-123", trace_id="trace-abc")
    token = set_current_context(ctx)
    try:
        active = current_context()
        assert active is ctx
        assert active.request_id == "req-123"
    finally:
        reset_current_context(token)

    assert current_context() is None
