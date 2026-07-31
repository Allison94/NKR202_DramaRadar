"""One-shot dev setup with mock Apify (no API cost).

    uv run python -m domains.review.run_dev_setup
"""

from __future__ import annotations

import json

from domains.review.seed_ai_analysis import seed_ai_analysis
from domains.review.seed_stores import seed_stores
from domains.review.service import run_daily_fetch, run_initial_fetch
from domains.store.service import get_dashboard_dataframe


def main() -> None:
    from db.apply_schema import apply_schema

    print("[1/5] schema …")
    try:
        apply_schema()
    except Exception as exc:
        print(f"      skip: {exc}")

    print("[2/5] store …")
    n = seed_stores()
    print(f"      {n} stores")

    print("[3/5] mock initial …")
    initial = run_initial_fetch(store_limit=n, use_mock=True)
    print(f"      review +{initial['etl']['review_upserted']}")

    print("[4/5] mock daily …")
    daily = run_daily_fetch(store_limit=n, use_mock=True)
    print(f"      review +{daily['etl']['review_upserted']}")

    print("[5/5] ai_analysis + dashboard check …")
    seed_ai_analysis()
    df = get_dashboard_dataframe()
    print(json.dumps({"dashboard_rows": len(df), "source": df["__data_source"].iloc[0] if len(df) else "empty"}, ensure_ascii=False))
    print("Done → streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()
