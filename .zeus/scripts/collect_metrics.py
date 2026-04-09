#!/usr/bin/env python3
"""
collect_metrics.py — 通用 AI-CLI 版 Zeus 指标采集器
替代 collect-metrics.sh，适用于任何不具备 bash 的 AI 编程助手
（Kimi、GLM、DeepSeek、GPT/Codex、Gemini 等）

支持数据源：
  - SQLite（内置 sqlite3）
  - PostgreSQL（需安装 psycopg2-binary）
  - Google Analytics CSV 导出（内置 csv）
  - 通用 HTTP API（内置 urllib）

使用方式：
  python .zeus/scripts/collect_metrics.py [--source sqlite|postgres|csv|api] [--out FILE]
"""

import argparse
import csv
import io
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Fix Windows console encoding for emoji/unicode output
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


class MetricsCollector:
    def __init__(self, version: str = "main"):
        self.version = version
        self.base_dir = Path(f".zeus/{version}")
        self.metrics: dict[str, Any] = {
            "pv": None,
            "uv": None,
            "conversion_rate": None,
            "revenue": None,
            "notes": "",
        }
        self.source_detail = "none"

    def _collect_sqlite(self, db_path: str | Path) -> bool:
        import sqlite3

        db = Path(db_path)
        if not db.exists():
            return False

        try:
            conn = sqlite3.connect(str(db))
            cursor = conn.cursor()

            # page_views count in last 7 days
            try:
                cursor.execute(
                    "SELECT COUNT(*) FROM page_views WHERE created_at > datetime('now', '-7 days')"
                )
                self.metrics["pv"] = cursor.fetchone()[0]
            except Exception:
                pass

            # unique users in last 7 days
            try:
                cursor.execute(
                    "SELECT COUNT(DISTINCT user_id) FROM page_views WHERE created_at > datetime('now', '-7 days')"
                )
                self.metrics["uv"] = cursor.fetchone()[0]
            except Exception:
                pass

            # conversion rate
            try:
                cursor.execute(
                    """
                    SELECT ROUND(
                        CAST(COUNT(DISTINCT user_id) AS FLOAT) /
                        NULLIF((SELECT COUNT(DISTINCT visitor_id) FROM sessions WHERE created_at > datetime('now', '-7 days')), 0)
                        * 100, 2
                    )
                    FROM users WHERE created_at > datetime('now', '-7 days')
                    """
                )
                self.metrics["conversion_rate"] = cursor.fetchone()[0]
            except Exception:
                pass

            conn.close()
            self.source_detail = f"SQLite: {db}"
            return True
        except Exception as e:
            print(f"⚠️  SQLite 采集失败: {e}")
            return False

    def _collect_postgres(self, dsn: str) -> bool:
        try:
            import psycopg2
        except ImportError:
            print("⚠️  未找到 psycopg2，跳过 PostgreSQL 采集。安装: pip install psycopg2-binary")
            return False

        try:
            conn = psycopg2.connect(dsn)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    "SELECT COUNT(*) FROM page_views WHERE created_at > NOW() - INTERVAL '7 days'"
                )
                self.metrics["pv"] = cursor.fetchone()[0]
            except Exception:
                pass

            try:
                cursor.execute(
                    "SELECT COUNT(DISTINCT user_id) FROM sessions WHERE created_at > NOW() - INTERVAL '7 days'"
                )
                self.metrics["uv"] = cursor.fetchone()[0]
            except Exception:
                pass

            try:
                cursor.execute(
                    """
                    SELECT ROUND(
                        CAST(COUNT(DISTINCT user_id) AS FLOAT) /
                        NULLIF((SELECT COUNT(DISTINCT visitor_id) FROM sessions WHERE created_at > NOW() - INTERVAL '7 days'), 0)
                        * 100, 2
                    )
                    FROM users WHERE created_at > NOW() - INTERVAL '7 days'
                    """
                )
                self.metrics["conversion_rate"] = cursor.fetchone()[0]
            except Exception:
                pass

            conn.close()
            self.source_detail = "PostgreSQL"
            return True
        except Exception as e:
            print(f"⚠️  PostgreSQL 采集失败: {e}")
            return False

    def _collect_csv(self, csv_path: str | Path) -> bool:
        path = Path(csv_path)
        if not path.exists():
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if not rows:
                return False

            row = rows[0]
            # Attempt common GA export column names
            if "Page views" in row:
                self.metrics["pv"] = self._parse_number(row["Page views"])
            elif "pv" in row:
                self.metrics["pv"] = self._parse_number(row["pv"])

            if "Users" in row:
                self.metrics["uv"] = self._parse_number(row["Users"])
            elif "uv" in row:
                self.metrics["uv"] = self._parse_number(row["uv"])

            if "Conversion rate" in row:
                self.metrics["conversion_rate"] = self._parse_number(row["Conversion rate"])
            elif "conversion_rate" in row:
                self.metrics["conversion_rate"] = self._parse_number(row["conversion_rate"])

            self.source_detail = f"Google Analytics CSV export: {path}"
            return True
        except Exception as e:
            print(f"⚠️  CSV 解析失败: {e}")
            return False

    def _collect_api(self, endpoint: str, token: str | None = None) -> bool:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = f"{endpoint.rstrip('/')}/metrics?period=7d"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))

            self.metrics["pv"] = data.get("pv")
            self.metrics["uv"] = data.get("uv")
            self.metrics["conversion_rate"] = data.get("conversion_rate")
            self.metrics["revenue"] = data.get("revenue")
            self.source_detail = f"HTTP API: {endpoint}"
            return True
        except urllib.error.HTTPError as e:
            print(f"⚠️  API 请求失败: {e.code} {e.reason}")
            return False
        except Exception as e:
            print(f"⚠️  API 采集失败: {e}")
            return False

    @staticmethod
    def _parse_number(value: Any) -> int | float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return value
        try:
            s = str(value).replace(",", "").replace("%", "").strip()
            if "." in s:
                return float(s)
            return int(s)
        except ValueError:
            return None

    def collect(
        self,
        source: str | None = None,
        db_path: str | None = None,
        dsn: str | None = None,
        csv_path: str | None = None,
        api_endpoint: str | None = None,
        api_token: str | None = None,
    ) -> dict[str, Any]:
        collected = False

        if source == "sqlite" or (source is None and db_path):
            target = db_path or "./db.sqlite"
            collected = self._collect_sqlite(target) or collected

        if source == "postgres" or (source is None and dsn):
            target = dsn or os.environ.get("DATABASE_URL", "")
            if target:
                collected = self._collect_postgres(target) or collected

        if source == "csv" or (source is None and csv_path):
            target = csv_path or ".zeus/ga-export.csv"
            collected = self._collect_csv(target) or collected

        if source == "api" or (source is None and api_endpoint):
            target = api_endpoint or os.environ.get("METRICS_API_URL", "")
            if target:
                token = api_token or os.environ.get("METRICS_API_TOKEN")
                collected = self._collect_api(target, token) or collected

        if not collected:
            self.metrics["notes"] = "未配置数据源。请编辑 .zeus/scripts/collect_metrics.py 接入实际数据，或通过命令行参数指定数据源。"
            self.source_detail = "none"

        return {
            "collected_at": now_iso(),
            "source_detail": self.source_detail,
            "metrics": self.metrics,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Zeus Metrics Collector (Python)")
    parser.add_argument("--source", choices=["sqlite", "postgres", "csv", "api"], default=None, help="指定数据源")
    parser.add_argument("--db", default=None, help="SQLite 数据库路径")
    parser.add_argument("--dsn", default=None, help="PostgreSQL DSN/连接字符串")
    parser.add_argument("--csv", default=None, help="GA CSV 导出文件路径")
    parser.add_argument("--api", default=None, help="HTTP API 基础地址")
    parser.add_argument("--token", default=None, help="HTTP API Bearer Token")
    parser.add_argument("--out", default=None, help="输出 JSON 文件路径（默认自动生成）")
    parser.add_argument("--version", default="main", help="Zeus 版本 (默认: main)")

    args = parser.parse_args()

    collector = MetricsCollector(version=args.version)
    result = collector.collect(
        source=args.source,
        db_path=args.db,
        dsn=args.dsn,
        csv_path=args.csv,
        api_endpoint=args.api,
        api_token=args.token,
    )

    out_path = Path(args.out) if args.out else Path(f".zeus/collected-metrics-{now_compact()}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 指标数据已写入: {out_path}")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
