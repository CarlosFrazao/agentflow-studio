"""TDD tests for FEAT-004: confidence_score preservation in /run.

ADR A4: run_card must only overwrite card.confidence_score when the
dispatched agent returns confidence > 0. Otherwise the value set by the
Reviewer (which runs before planner/dev) would be zeroed by the next
agent in the pipeline, breaking auto-approve.

RED phase: these fail because run.py:148 unconditionally assigns
`card.confidence_score = confidence`.
"""

import pytest

pytestmark = pytest.mark.asyncio


async def _seed_card_in_reviewing(client) -> tuple[str, str]:
    """Seed a project + card already positioned at the 'reviewing' column."""
    proj = await client.post("/api/v1/projects", json={"name": "P"})
    pid = proj.json()["data"]["id"]
    card = await client.post(
        "/api/v1/cards",
        json={"project_id": pid, "title": "Ideia", "column": "reviewing"},
    )
    return pid, card.json()["data"]["id"]


async def test_confidence_preserved_when_zero(
    client, monkeypatch
) -> None:
    """Reviewer in 'reviewing' sets 0.8; dev in 'production' returns 0.0.

    After two runs (reviewer -> production -> dev), the card must keep 0.8.
    """
    from app.api.v1 import run as run_module

    async def fake_dispatch(agent_name, card, *args, **kwargs):
        if agent_name == "reviewer":
            return {
                "content": '{"passed": true}',
                "confidence": 0.8,
                "critical_alerts": 0,
                "target_column": "production",
            }
        # dev / later agent returns 0.0 confidence (no confidence signal).
        return {
            "content": '{"code": "x"}',
            "confidence": 0.0,
            "critical_alerts": 0,
        }

    monkeypatch.setattr(run_module, "_dispatch", fake_dispatch)

    _, cid = await _seed_card_in_reviewing(client)

    # Run 1: reviewer sets confidence 0.8 and advances to 'production'.
    resp1 = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp1.status_code == 200
    card1 = (await client.get(f"/api/v1/cards/{cid}")).json()["data"]
    assert card1["column"] == "production"
    assert card1["confidence_score"] == 0.8

    # Run 2: dev returns confidence 0.0 -> must NOT zero the reviewer's 0.8.
    resp2 = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp2.status_code == 200
    card2 = (await client.get(f"/api/v1/cards/{cid}")).json()["data"]
    assert card2["confidence_score"] == 0.8


async def test_confidence_overwritten_when_positive(
    client, monkeypatch
) -> None:
    """Reviewer in 'reviewing' sets 0.8; dev in 'production' returns 0.9.

    After two runs, the positive confidence from dev must overwrite 0.8.
    """
    from app.api.v1 import run as run_module

    async def fake_dispatch(agent_name, card, *args, **kwargs):
        if agent_name == "reviewer":
            return {
                "content": '{"passed": true}',
                "confidence": 0.8,
                "critical_alerts": 0,
                "target_column": "production",
            }
        return {
            "content": '{"code": "x"}',
            "confidence": 0.9,
            "critical_alerts": 0,
        }

    monkeypatch.setattr(run_module, "_dispatch", fake_dispatch)

    _, cid = await _seed_card_in_reviewing(client)

    resp1 = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp1.status_code == 200
    assert (await client.get(f"/api/v1/cards/{cid}")).json()["data"][
        "confidence_score"
    ] == 0.8

    resp2 = await client.post(f"/api/v1/cards/{cid}/run")
    assert resp2.status_code == 200
    card2 = (await client.get(f"/api/v1/cards/{cid}")).json()["data"]
    # positive confidence from the later agent overwrites.
    assert card2["confidence_score"] == 0.9
