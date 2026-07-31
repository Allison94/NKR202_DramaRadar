"""Step 1-1: test Apify or mock connectivity."""

from __future__ import annotations

import os


def test_connection(*, use_mock: bool | None = None) -> dict[str, str]:
    if use_mock is None:
        use_mock = os.getenv("REVIEW_USE_MOCK", "true").lower() in {"1", "true", "yes"}

    if use_mock:
        from domains.review.mock_client import test_mock_connection

        return test_mock_connection()

    from domains.review.client import ACTOR_ID, client

    actor = client.actor(ACTOR_ID).get()
    name = actor.get("name") if isinstance(actor, dict) else getattr(actor, "name", ACTOR_ID)
    return {
        "status": "ok",
        "actor_id": ACTOR_ID,
        "actor_name": str(name),
        "message": "Apify token 有效，Review Actor 可連線。",
    }


if __name__ == "__main__":
    print(test_connection())
