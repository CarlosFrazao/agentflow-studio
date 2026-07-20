"""FEAT-007 (B2-1): POST /cards must reject a card whose project is orphaned.

`Project.user_id` is nullable (models/project.py:16). A project with
`user_id=None` belongs to no tenant, so any authenticated user must be denied
the ability to attach a card to it — otherwise a tenant-escalation / data
cross-contamination gap opens. `create_card` revalidates
`project.user_id == user.id`, which covers the NULL case (`None != user.id`).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def _seed_orphan_project(session_factory, name: str = "Orfao") -> str:
    """Persists a Project with user_id=None (no tenant) and returns its id."""
    async with session_factory() as s:
        project = Project(name=name, user_id=None)
        s.add(project)
        await s.commit()
        await s.refresh(project)
        return str(project.id)


async def test_create_card_rejects_orphan_project(
    client: AsyncClient, session_factory
) -> None:
    """A card targeting a project with user_id=None must be rejected (422)."""
    pid = await _seed_orphan_project(session_factory)
    resp = await client.post(
        "/api/v1/cards", json={"project_id": pid, "title": "Card em orfao"}
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["success"] is False
    # `error` may be a dict (standard envelope); normalize to string.
    err = body["error"]
    err_str = err["message"] if isinstance(err, dict) else err
    assert "project_id" in err_str.lower()


async def test_create_card_rejects_other_users_project(
    client: AsyncClient, session_factory
) -> None:
    """Defense-in-depth: a card for another user's project is rejected (422).

    `get_owned_project`/inline check both enforce `project.user_id == user.id`;
    this guards against a future relaxation of either check.
    """
    # Seed a second user and a project owned by them.
    async with session_factory() as s:
        other = User(
            email="other-owner@example.com", display_name="Other", password_hash=None
        )
        s.add(other)
        await s.commit()
        await s.refresh(other)
        project = Project(name="Alheio", user_id=other.id)
        s.add(project)
        await s.commit()
        await s.refresh(project)
        pid = str(project.id)

    # The authenticated client (different user) must not attach a card.
    resp = await client.post(
        "/api/v1/cards", json={"project_id": pid, "title": "Card em proj alheio"}
    )
    assert resp.status_code == 422, resp.text


async def test_create_card_accepts_owned_project(
    client: AsyncClient, session_factory
) -> None:
    """Sanity: a card for the caller's own project still succeeds (201)."""
    async with session_factory() as s:
        user = (await s.scalars(select(User))).first()
        project = Project(name="Proprio", user_id=user.id)
        s.add(project)
        await s.commit()
        await s.refresh(project)
        pid = str(project.id)

    resp = await client.post(
        "/api/v1/cards", json={"project_id": pid, "title": "Card no proprio"}
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["title"] == "Card no proprio"
