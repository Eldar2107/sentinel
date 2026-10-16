"""
Sentinel — Verilənlər Bazası Qatı
asyncpg + SQLAlchemy asinxron interfeysi.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import asyncpg


class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.dsn = os.getenv("DATABASE_URL", "postgresql://sentinel:sentinel_secret@postgres:5432/sentinel")

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            self.dsn,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        print("Verilənlər bazası bağlantısı quruldu.")

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    # ─── Test Nəticələri ──────────────────────────────────────────────────────

    async def save_test_result(self, result: dict):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO test_results
                    (bank_id, status_code, response_body, response_headers,
                     latency_ms, is_compliant, compliance_issues)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
                result["bank_id"],
                result.get("status_code", 0),
                json.dumps(result.get("body") or {}),
                json.dumps(result.get("headers") or {}),
                result.get("latency_ms", 0),
                result.get("is_compliant", False),
                json.dumps(result.get("compliance_issues") or []),
            )

    async def get_test_results(self, bank_id: str, limit: int = 50) -> list:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM test_results
                WHERE bank_id = $1
                ORDER BY tested_at DESC
                LIMIT $2
            """, bank_id, limit)
            return [dict(r) for r in rows]

    # ─── Latency Metriklər ────────────────────────────────────────────────────

    async def save_latency_metrics(self, bank_id: str, p50: float, p95: float, p99: float):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO latency_metrics (bank_id, latency_ms, p50, p95, p99)
                VALUES ($1, $2, $3, $4, $5)
            """, bank_id, p50, p50, p95, p99)

    async def get_latency_history(self, bank_id: str, hours: int = 24) -> list:
        async with self.pool.acquire() as conn:
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
            rows = await conn.fetch("""
                SELECT p50, p95, p99, measured_at
                FROM latency_metrics
                WHERE bank_id = $1 AND measured_at > $2
                ORDER BY measured_at
            """, bank_id, since)
            return [dict(r) for r in rows]

    async def get_latest_latency(self, bank_id: str) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT p50, p95, p99, measured_at
                FROM latency_metrics
                WHERE bank_id = $1
                ORDER BY measured_at DESC
                LIMIT 1
            """, bank_id)
            return dict(row) if row else None

    # ─── Uptime ───────────────────────────────────────────────────────────────

    async def save_uptime(self, bank_id: str, is_up: bool, status_code: int, error: str = None):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO uptime_records (bank_id, is_up, status_code, error_message)
                VALUES ($1, $2, $3, $4)
            """, bank_id, is_up, status_code, error)

    async def get_uptime_history(self, bank_id: str, hours: int = 24) -> list:
        async with self.pool.acquire() as conn:
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
            rows = await conn.fetch("""
                SELECT is_up, status_code, checked_at
                FROM uptime_records
                WHERE bank_id = $1 AND checked_at > $2
                ORDER BY checked_at
            """, bank_id, since)
            return [dict(r) for r in rows]

    # ─── Drift Hadisələri ─────────────────────────────────────────────────────

    async def save_drift_event(self, bank_id: str, endpoint: str, diff: dict):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO drift_events
                    (bank_id, endpoint, drift_type, field_path, expected_value, actual_value, severity)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
                bank_id,
                endpoint,
                diff.get("drift_type"),
                diff.get("field_path"),
                str(diff.get("expected")),
                str(diff.get("actual")),
                diff.get("severity", "warning"),
            )

    async def get_drift_events(self, bank_id: str = None, limit: int = 50) -> list:
        async with self.pool.acquire() as conn:
            if bank_id:
                rows = await conn.fetch("""
                    SELECT * FROM drift_events
                    WHERE bank_id = $1
                    ORDER BY detected_at DESC
                    LIMIT $2
                """, bank_id, limit)
            else:
                rows = await conn.fetch("""
                    SELECT * FROM drift_events
                    ORDER BY detected_at DESC
                    LIMIT $1
                """, limit)
            return [dict(r) for r in rows]

    # ─── Bank Skorları ────────────────────────────────────────────────────────

    async def save_bank_score(self, bank_id: str, score: dict):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO bank_scores
                    (bank_id, compliance_score, reliability_score, latency_score,
                     security_score, total_score, score_breakdown)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
                bank_id,
                score.get("compliance_score", 0),
                score.get("reliability_score", 0),
                score.get("latency_score", 0),
                score.get("security_score", 0),
                score.get("total_score", 0),
                json.dumps(score),
            )

    async def get_latest_score(self, bank_id: str) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM bank_scores
                WHERE bank_id = $1
                ORDER BY calculated_at DESC
                LIMIT 1
            """, bank_id)
            if row:
                data = dict(row)
                if isinstance(data.get("score_breakdown"), str):
                    data["score_breakdown"] = json.loads(data["score_breakdown"])
                return data
            return None

    # ─── Anomaliyalar ─────────────────────────────────────────────────────────

    async def save_anomaly(self, bank_id: str, anomaly_type: str, severity: str,
                           metric_value: float, baseline_value: float):
        async with self.pool.acquire() as conn:
            deviation = (metric_value / baseline_value - 1) if baseline_value > 0 else 0
            await conn.execute("""
                INSERT INTO anomalies
                    (bank_id, anomaly_type, severity, metric_value, baseline_value, deviation_factor)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, bank_id, anomaly_type, severity, metric_value, baseline_value, deviation)

    async def get_anomalies(self, bank_id: str = None, limit: int = 50) -> list:
        async with self.pool.acquire() as conn:
            if bank_id:
                rows = await conn.fetch("""
                    SELECT * FROM anomalies
                    WHERE bank_id = $1
                    ORDER BY detected_at DESC
                    LIMIT $2
                """, bank_id, limit)
            else:
                rows = await conn.fetch("""
                    SELECT * FROM anomalies
                    ORDER BY detected_at DESC
                    LIMIT $1
                """, limit)
            return [dict(r) for r in rows]


# Singleton
db = Database()
