"""Regression test for the precision of the generated ``ctx`` annotation.

The protoc plugin must emit ``ctx: RequestContext[Input, Output]`` for every service
handler, not a bare ``RequestContext``. A bare generic is an implicit
``RequestContext[Any, Any]`` (``ty`` infers ``RequestContext[Unknown, Unknown]``), which
trips strict-mypy consumers running ``disallow_any_generics`` with "Missing type
parameters for generic type RequestContext".

The context's type params must always be the BARE message types and must agree with the
method's ``MethodInfo(input=..., output=...)`` -- even for streaming methods, whose
request/return are wrapped in ``AsyncIterator``/``Iterator`` but whose ``ctx`` is not.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import get_args, get_origin, get_type_hints

import pytest

from connectrpc.request import RequestContext

from .haberdasher_connect import Haberdasher, HaberdasherSync
from .haberdasher_pb2 import Hat, Size

# The generated module imports these names only under ``if TYPE_CHECKING`` and uses
# ``from __future__ import annotations``, so its annotations are strings. Supply the
# missing names so ``get_type_hints`` can resolve them. (The ``*_pb2`` modules are real
# runtime imports already present in the handler's ``__globals__``.)
_NS = {
    "RequestContext": RequestContext,
    "AsyncIterator": AsyncIterator,
    "Iterator": Iterator,
}

# (handler method name, expected (Input, Output) message types for the ctx type params)
_CASES = [
    ("make_hat", (Size, Hat)),  # unary
    ("make_flexible_hat", (Size, Hat)),  # client streaming
    ("make_similar_hats", (Size, Hat)),  # server streaming
    ("make_various_hats", (Size, Hat)),  # bidi streaming
]


@pytest.mark.parametrize("protocol", [Haberdasher, HaberdasherSync])
@pytest.mark.parametrize(("method_name", "expected"), _CASES)
def test_handler_ctx_is_precisely_parameterized(
    protocol: type, method_name: str, expected: tuple[type, type]
) -> None:
    method = getattr(protocol, method_name)
    ctx = get_type_hints(method, localns=_NS)["ctx"]

    assert get_origin(ctx) is RequestContext, (
        f"{protocol.__name__}.{method_name}: ctx must be a parameterized "
        f"RequestContext[...], not bare {ctx!r}"
    )
    assert get_args(ctx) == expected, (
        f"{protocol.__name__}.{method_name}: ctx type params must be the bare message "
        f"types {expected!r} (never AsyncIterator/Iterator-wrapped), got {get_args(ctx)!r}"
    )
