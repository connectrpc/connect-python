from __future__ import annotations

import pytest

from connectrpc.request import Headers


def test_headers_no_duplicates() -> None:
    h = Headers()
    assert len(h) == 0
    assert list(h.items()) == []
    assert list(h.keys()) == []
    assert list(h.values()) == []
    assert "foo" not in h
    with pytest.raises(KeyError):
        _ = h["missing"]
    assert h.getall("missing") == ()

    h["Content-Type"] = "application/json"
    h["X-Test"] = "foo"
    assert h["content-type"] == "application/json"
    assert h["CONTENT-TYPE"] == "application/json"
    assert h.getall("content-type") == ["application/json"]
    assert h.getall("X-Test") == ["foo"]
    assert h["X-Test"] == "foo"
    assert "content-type" in h
    assert "CONTENT-TYPE" in h
    assert "x-test" in h
    assert len(h) == 2
    assert list(h.items()) == [("content-type", "application/json"), ("x-test", "foo")]
    assert list(h.allitems()) == [
        ("content-type", "application/json"),
        ("x-test", "foo"),
    ]
    assert list(h.keys()) == ["content-type", "x-test"]
    assert list(h.values()) == ["application/json", "foo"]
    h["content-type"] = "text/plain"
    assert h["Content-Type"] == "text/plain"
    assert list(h.items()) == [("content-type", "text/plain"), ("x-test", "foo")]
    assert list(h.allitems()) == [("content-type", "text/plain"), ("x-test", "foo")]
    assert list(h.keys()) == ["content-type", "x-test"]
    assert list(h.values()) == ["text/plain", "foo"]
    del h["CONTENT-TYPE"]
    assert "content-type" not in h
    assert len(h) == 1
    h.clear()
    assert len(h) == 0
    assert list(h.items()) == []


def test_headers_duplicates() -> None:
    h = Headers()
    h.add("X-Test", "foo")
    h.add("X-Test", "bar")
    assert len(h) == 1
    assert h["x-test"] == "foo"
    assert h.getall("x-test") == ["foo", "bar"]
    assert list(h.items()) == [("x-test", "foo")]
    assert list(h.keys()) == ["x-test"]
    assert list(h.values()) == ["foo"]
    assert list(h.allitems()) == [("x-test", "foo"), ("x-test", "bar")]
    h.add("X-Test", "baz")
    assert len(h) == 1
    assert list(h.items()) == [("x-test", "foo")]
    assert list(h.keys()) == ["x-test"]
    assert list(h.values()) == ["foo"]
    assert list(h.allitems()) == [
        ("x-test", "foo"),
        ("x-test", "bar"),
        ("x-test", "baz"),
    ]
    assert h.getall("x-test") == ["foo", "bar", "baz"]
    h["authorization"] = "cookie"
    assert h["authorization"] == "cookie"
    assert list(h.items()) == [("x-test", "foo"), ("authorization", "cookie")]
    assert list(h.keys()) == ["x-test", "authorization"]
    assert list(h.values()) == ["foo", "cookie"]
    assert list(h.allitems()) == [
        ("x-test", "foo"),
        ("x-test", "bar"),
        ("x-test", "baz"),
        ("authorization", "cookie"),
    ]
    del h["x-test"]
    assert "x-test" not in h
    assert len(h) == 1
    h["x-Test"] = "again"
    assert h["x-test"] == "again"
    assert list(h.allitems()) == [("authorization", "cookie"), ("x-test", "again")]
    h.add("x-test", "and again")
    # Implemented by base class using dunder methods
    h.pop("x-test", None)
    assert list(h.allitems()) == [("authorization", "cookie")]
    h.add("x-animal", "bear")
    h.add("x-animal", "cat")
    h.update({"x-animal": "dog"})
    assert list(h.allitems()) == [("authorization", "cookie"), ("x-animal", "dog")]
    assert h.getall("x-animal") == ["dog"]
