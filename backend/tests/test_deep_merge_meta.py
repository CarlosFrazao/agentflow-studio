"""Tests for deep-merge of Card.meta on PATCH /cards (FEAT-010)."""

from app.api.v1.cards import _deep_merge_meta


def test_deep_merge_meta_preserves_sibling_subkeys():
    base = {"review_logs": {"a": 1, "b": 2}, "phase": "research"}
    incoming = {"review_logs": {"b": 3}}
    merged = _deep_merge_meta(base, incoming)
    assert merged["review_logs"] == {"a": 1, "b": 3}
    assert merged["phase"] == "research"


def test_deep_merge_meta_nested_levels():
    base = {"x": {"y": {"z": 1}}}
    incoming = {"x": {"y": {"w": 2}}}
    merged = _deep_merge_meta(base, incoming)
    assert merged["x"]["y"] == {"z": 1, "w": 2}


def test_deep_merge_meta_scalar_replaces():
    base = {"phase": "research", "count": 1}
    incoming = {"phase": "planning", "count": 5}
    merged = _deep_merge_meta(base, incoming)
    assert merged["phase"] == "planning"
    assert merged["count"] == 5


def test_deep_merge_meta_list_replaces_wholesale():
    base = {"tags": ["a", "b"]}
    incoming = {"tags": ["c"]}
    merged = _deep_merge_meta(base, incoming)
    assert merged["tags"] == ["c"]


def test_deep_merge_meta_empty_incoming_keeps_base():
    base = {"a": 1}
    merged = _deep_merge_meta(base, {})
    assert merged == {"a": 1}


def test_deep_merge_meta_new_top_level_key_added():
    base = {"a": 1}
    incoming = {"b": 2}
    merged = _deep_merge_meta(base, incoming)
    assert merged == {"a": 1, "b": 2}
