"""Test Apify Review Actor connectivity (no mock)."""

from __future__ import annotations

from domains.review.client import ACTOR_ID, client
from domains.review.logging_setup import get_logger

log = get_logger(__name__)


def test_connection() -> dict[str, str]:
    try:
        actor = client.actor(ACTOR_ID).get()
        name = (
            actor.get("name")
            if isinstance(actor, dict)
            else getattr(actor, "name", ACTOR_ID)
        )
        result = {
            "status": "ok",
            "actor_id": ACTOR_ID,
            "actor_name": str(name),
            "message": "Apify token 有效，Review Actor 可連線。",
        }
        log.info("test_connection ok actor=%s", name)
        return result
    except Exception as exc:
        log.exception("test_connection failed")
        return {
            "status": "error",
            "actor_id": ACTOR_ID,
            "message": str(exc),
        }


if __name__ == "__main__":
    print(test_connection())
