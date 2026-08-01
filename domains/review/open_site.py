"""One command: check DB + seed pr_reply + start Streamlit.

Usage (Dev Container terminal):

    uv run python -m domains.review.open_site

If 8501 is busy, automatically tries 8502 / 8503.
Open the Local URL printed at the end in Chrome.
"""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


def _pick_port() -> int:
    for port in (8501, 8502, 8503, 8510):
        if _port_free(port):
            return port
    raise RuntimeError("8501–8510 都被占用，請先關掉舊的 Streamlit 視窗/終端機")


def _print_db_status() -> None:
    print("=" * 50)
    print("0) 確認是否連到 PostgreSQL（不是假資料殼）")
    print("=" * 50)
    try:
        from sqlalchemy import text

        from db.database import engine

        url = engine.url
        print(f"   連線 host={url.host}  database={url.database}  user={url.username}")
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            store_n = connection.execute(text('SELECT COUNT(*) FROM "store"')).scalar()
            review_n = connection.execute(text('SELECT COUNT(*) FROM "review"')).scalar()
            ai_n = connection.execute(text('SELECT COUNT(*) FROM "ai_analysis"')).scalar()
        print(f"   OK 已連線 → store={store_n}, review={review_n}, ai_analysis={ai_n}")
        print("   說明：網頁資料來自這顆 DB。")
        print("   若你/組長剛建空庫，數字會是 0，畫面也會是空的。")
        print("   現在有數字 = 先前 seed / pipeline 有寫進去（仍是 DB，不是網頁假資料）。")
    except Exception as exc:
        print(f"   連線失敗：{exc}")
        print("   → 先確認 Docker db 有開，再重跑。")


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    _print_db_status()

    print()
    print("=" * 50)
    print("1) 寫入 ai_analysis.pr_reply（測試用）")
    print("=" * 50)
    try:
        from domains.review.seed_ai_analysis import seed_ai_analysis

        n = seed_ai_analysis()
        print(f"   已寫入 {n} 筆到資料庫表 ai_analysis")
    except Exception as exc:
        print(f"   seed 略過：{exc}")

    try:
        port = _pick_port()
    except RuntimeError as exc:
        print(str(exc))
        return 1

    print()
    print("=" * 50)
    print(f"2) 啟動網頁（port {port}）")
    print(f"   成功後用 Chrome 開： http://localhost:{port}")
    print("   這個終端機不要關")
    print("=" * 50)
    print()

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "dashboard/app.py",
        "--server.address",
        "0.0.0.0",
        "--server.port",
        str(port),
        "--browser.gatherUsageStats",
        "false",
    ]
    return subprocess.call(cmd, cwd=str(project_root))


if __name__ == "__main__":
    raise SystemExit(main())
