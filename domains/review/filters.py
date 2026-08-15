"""Review ETL filters: dedup, validation, generic PR detection.

Business rules:
- Only 1-star / 2-star reviews enter the business review table.
- Reviews without owner reply are still kept for owner-reply recheck.
- Owner replies with >= 80% similarity to generic PR templates are excluded.
- Stores that trigger generic PR detection will later be marked
  store.skip_review_fetch = TRUE by repository/service.
"""

from __future__ import annotations

import difflib
import re
from typing import Any


GENERIC_PR_TEMPLATES: tuple[str, ...] = (
    "非常抱歉讓您有不愉快的用餐體驗，我們會持續改善。",
    "感謝您的寶貴意見，我們會持續改進服務品質。",
    "很抱歉此次消費體驗未能符合您的期待，我們會重新檢視流程。",
    "謝謝您願意提供意見，我們會持續努力提供更好的服務。",
    "對於造成您的不便，我們深感抱歉，並會持續改善。",
    "感謝您的回饋，我們已收到並會進一步了解狀況。",
)

SIMILARITY_THRESHOLD = 0.80
MIN_REVIEW_TEXT_LEN = 2


def text_similarity(left: str, right: str) -> float:
    """Return normalized text similarity from 0.0 to 1.0."""

    left_norm = re.sub(r"\s+", "", left.strip())
    right_norm = re.sub(r"\s+", "", right.strip())

    if not left_norm or not right_norm:
        return 0.0

    return difflib.SequenceMatcher(
        None,
        left_norm,
        right_norm,
    ).ratio()


def is_generic_pr_reply(owner_text: object) -> bool:
    """Generic PR reply = >= 80% similar to configured PR template."""

    if owner_text is None:
        return False

    text = str(owner_text).strip()
    if not text:
        return False

    for template in GENERIC_PR_TEMPLATES:
        similarity = text_similarity(text, template)

        if similarity >= SIMILARITY_THRESHOLD:
            return True

    return False


def validate_raw_item(raw: dict[str, Any]) -> tuple[bool, str]:
    if not raw.get("reviewId"):
        return False, "missing_review_id"

    if not raw.get("placeId"):
        return False, "missing_place_id"

    return True, "ok"


def should_write_business_review(
    review_row: dict[str, Any],
) -> tuple[bool, str]:
    """Decide whether a transformed review should enter review table."""

    text = str(review_row.get("text", "")).strip()

    if len(text) < MIN_REVIEW_TEXT_LEN:
        return False, "empty_review_text"

    stars = int(review_row.get("stars") or 0)

    # 正式 review table 只存 1★ / 2★
    if stars not in (1, 2):
        return False, "not_low_star_review"

    owner_reply = str(
        review_row.get("response_from_owner_text") or ""
    ).strip()

    # 沒有老闆回覆仍然要進 review，
    # 後續使用 owner_reply_recheck / next_check_at 補查。
    if not owner_reply:
        return True, "needs_owner_recheck"

    # >= 80% 制式公關回覆：
    # 此 Review 不進正式 review；
    # placeId 會由 ETL 回報給 service/repository，
    # 再更新 store.skip_review_fetch = TRUE。
    if is_generic_pr_reply(owner_reply):
        return False, "generic_pr_reply"

    return True, "ok"


def dedupe_raw_items(
    raw_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    skipped = 0

    for item in raw_items:
        if not isinstance(item, dict):
            skipped += 1
            continue

        review_id = item.get("reviewId")

        if not review_id:
            skipped += 1
            continue

        key = str(review_id)

        if key in seen:
            skipped += 1
            continue

        seen.add(key)
        kept.append(item)

    return kept, skipped