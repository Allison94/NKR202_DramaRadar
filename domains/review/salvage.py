"""救援已付費但沒入庫的 Apify run。

使用時機：DAG 已經啟動 Actor 之後才失敗（例如 sensor 拋例外），
Apify 那邊照樣把資料爬完、費用照算，但沒有人去把 dataset 收回來。
直接重跑 DAG 會啟動全新的 run，等於同一份資料付兩次錢。

本模組只讀取既有的 run 與 dataset，**不會啟動任何新的 Actor**，
所以不產生額外費用。Apify 的 dataset 保留 7 天，過期就救不回來。

同一套邏輯有兩個入口：

- Airflow UI 的 `review_salvage_dag_v1`（手動觸發，可填參數）
- 命令列，見下方

盤點最近的 run（不寫入資料庫，先看有哪些可救）：

    uv run python -m domains.review.salvage --list

指定 run 撈回來：

    uv run python -m domains.review.salvage --run-id zPhzScmx1uW9RjhLt

把最近 6 小時內所有可救的 run 一次撈完：

    uv run python -m domains.review.salvage --auto --hours 6
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from domains.review.client import list_runs
from domains.review.logging_setup import get_logger
from domains.review.repository import fetch_ingested_run_ids
from domains.review.service import salvage_finished_run


log = get_logger(__name__)


def parse_apify_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if not value:
        return None

    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _field(run: dict[str, Any], *names: str) -> Any:
    """apify-client 回傳 snake_case，REST API 原始格式是 camelCase，兩種都接。"""

    for name in names:
        value = run.get(name)
        if value not in (None, ""):
            return value

    return None


def run_started_at(run: dict[str, Any]) -> datetime | None:
    return parse_apify_time(_field(run, "started_at", "startedAt"))


def run_dataset_id(run: dict[str, Any]) -> str | None:
    value = _field(run, "default_dataset_id", "defaultDatasetId")
    return str(value) if value else None


def run_cost_usd(run: dict[str, Any]) -> float:
    """這個 run 已經花掉的錢，用來看「這筆錢救不救得回來」。"""

    try:
        return float(_field(run, "usage_total_usd", "usageTotalUsd") or 0)
    except (TypeError, ValueError):
        return 0.0


def find_salvageable_runs(
    *,
    hours: float = 24.0,
    limit: int = 100,
    include_ingested: bool = False,
) -> list[dict[str, Any]]:
    """找出「已成功跑完、但沒進資料庫」的 run。

    以 Apify 的 run 清單為準，因為它才知道實際有哪些 run 存在。
    再用 execution_log 的成功紀錄扣掉已經收過網的部分。
    """

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    already = set() if include_ingested else fetch_ingested_run_ids()

    found = []

    for run in list_runs(limit=limit):
        run_id = str(run.get("id") or "")
        started = run_started_at(run)

        if not run_id or str(run.get("status")) != "SUCCEEDED":
            continue

        if not started or started < cutoff:
            continue

        if run_id in already:
            continue

        found.append(run)

    return found


def salvage(
    run_ids: list[str],
    pipeline: str = "review_initial",
) -> list[dict[str, Any]]:
    results = []

    for run_id in run_ids:
        log.info("[salvage] 處理 run_id=%s", run_id)
        result = salvage_finished_run(run_id, pipeline=pipeline)
        results.append(result)

        if result.get("ingested"):
            log.info(
                "[salvage] run_id=%s 成功寫入 raw=%s etl=%s",
                run_id,
                result.get("raw_count"),
                result.get("etl"),
            )
        else:
            log.warning(
                "[salvage] run_id=%s 略過：%s（狀態 %s）",
                run_id,
                result.get("reason"),
                result.get("run_status"),
            )

    return results


def _print_runs(runs: list[dict[str, Any]], ingested: set[str]) -> None:
    header = (
        f"{'RUN ID':20} {'STATUS':12} {'STARTED (UTC)':21} "
        f"{'DATASET':20} {'USD':>8}  已入庫"
    )
    print(header)
    print("-" * len(header))

    for run in runs:
        started = run_started_at(run)
        run_id = str(run.get("id") or "")

        print(
            f"{run_id:20} "
            f"{str(run.get('status') or ''):12} "
            f"{started.strftime('%Y-%m-%d %H:%M:%S') if started else '':21} "
            f"{run_dataset_id(run) or '':20} "
            f"{run_cost_usd(run):>8.3f}  "
            f"{'是' if run_id in ingested else '否'}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "救援已付費但沒入庫的 Apify Review run（不會啟動新的 Actor，不產生費用）"
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="只列出最近的 run，不寫入資料庫",
    )
    parser.add_argument(
        "--run-id",
        action="append",
        default=[],
        metavar="RUN_ID",
        help="指定要撈回來的 run id，可重複指定多次",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="自動撈回指定時間範圍內所有可救的 run",
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=6.0,
        help="搭配 --auto / --list 使用，往回追溯幾小時（預設 6）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="向 Apify 查詢最近幾筆 run（預設 100）",
    )
    parser.add_argument(
        "--pipeline",
        default="review_initial",
        help="寫進 execution_log 的 pipeline 名稱（預設 review_initial）",
    )
    parser.add_argument(
        "--include-ingested",
        action="store_true",
        help="連已經入庫過的 run 也重撈（ETL 是 upsert，安全但多餘）",
    )

    args = parser.parse_args()

    if args.list:
        _print_runs(list_runs(limit=args.limit), fetch_ingested_run_ids())
        return

    run_ids = list(args.run_id)

    if args.auto:
        candidates = find_salvageable_runs(
            hours=args.hours,
            limit=args.limit,
            include_ingested=args.include_ingested,
        )

        run_ids.extend(str(run["id"]) for run in candidates)

        total_cost = sum(run_cost_usd(run) for run in candidates)
        print(
            f"--auto 命中 {len(candidates)} 個最近 {args.hours} 小時內"
            f"可救的 run，已花費 US${total_cost:.3f}"
        )

    # 去重但保留順序
    run_ids = list(dict.fromkeys(run_ids))

    if not run_ids:
        if args.auto:
            print("沒有可救的 run，不需要處理。")
            return

        parser.error("請用 --run-id 指定，或加上 --auto。先用 --list 盤點。")

    results = salvage(run_ids, args.pipeline)

    ingested = [r for r in results if r.get("ingested")]
    total_raw = sum(r.get("raw_count") or 0 for r in ingested)

    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    print(
        f"\n完成：{len(ingested)}/{len(results)} 個 run 已入庫，"
        f"共 {total_raw} 筆原始評論"
    )


if __name__ == "__main__":
    main()
