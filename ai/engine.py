"""
Sentinel — AI Mühərriki
A1: Sintetik data generatoru
A3: Gecikmə/xəta anomaliyası (Rolling MAD + Isolation Forest)
A9: Qiymətləndirmə dəsti
"""

import asyncio
import json
import os
import random
import time
from datetime import datetime, timezone, timedelta

import asyncpg
import numpy as np
import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sklearn.ensemble import IsolationForest

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sentinel:sentinel_secret@postgres:5432/sentinel")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

BANK_PROFILES = {
    "bank_a": {"base_latency": 120, "std": 18, "error_rate": 0.01},
    "bank_b": {"base_latency": 320, "std": 45, "error_rate": 0.05},
    "bank_c": {"base_latency": 750, "std": 120, "error_rate": 0.20},
}

pool: asyncpg.Pool = None
redis_client = None
scheduler = AsyncIOScheduler()


# ─── A1: Sintetik Məlumat Generatoru ─────────────────────────────────────────

def generate_synthetic_telemetry(bank_id: str, n_points: int = 200) -> list:
    """
    Bank profili əsasında sintetik telemetriya yarat.
    Qəsdən anomaliyalar: gecikmə sıçrayışı, xəta partlayışı, sxem dəyişikliyi.
    """
    profile = BANK_PROFILES[bank_id]
    rng = np.random.default_rng(42)
    data = []

    base_time = datetime.now(timezone.utc) - timedelta(hours=n_points // 12)

    for i in range(n_points):
        t = base_time + timedelta(minutes=i * 5)
        latency = max(10, rng.normal(profile["base_latency"], profile["std"]))
        is_error = rng.random() < profile["error_rate"]
        schema_drift = False
        label = "normal"

        # Qəsdən anomaliyalar
        if bank_id == "bank_b" and 80 <= i < 100:
            # Gecikmə sıçrayışı
            latency = profile["base_latency"] * rng.uniform(3.5, 6.0)
            label = "latency_spike"
        elif bank_id == "bank_c" and 120 <= i < 135:
            # Xəta partlayışı
            is_error = True
            label = "error_burst"
        elif bank_id == "bank_b" and i == 150:
            # Sxem dəyişikliyi
            schema_drift = True
            label = "schema_change"

        data.append({
            "bank_id": bank_id,
            "timestamp": t.isoformat(),
            "latency_ms": round(latency, 2),
            "is_error": is_error,
            "schema_drift": schema_drift,
            "label": label,
        })

    return data


# ─── A3: Anomaliya Aşkarlama ──────────────────────────────────────────────────

class AnomalyDetector:
    """
    İki metodla anomaliya aşkarlama:
    1. Rolling MAD (Median Absolute Deviation) — sadə, deterministik
    2. Isolation Forest — ML əsaslı, bənzərsiz anomaliyalar üçün
    """

    def __init__(self, window: int = 20, threshold: float = 3.5):
        self.window = window
        self.threshold = threshold
        self.iso_forest = IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=42,
        )
        self._is_fitted = False

    def rolling_mad_detect(self, values: list[float]) -> list[dict]:
        """Rolling MAD anomaliya aşkarlaması."""
        if len(values) < self.window:
            return []

        arr = np.array(values)
        anomalies = []

        for i in range(self.window, len(arr)):
            window_data = arr[i - self.window:i]
            median = np.median(window_data)
            mad = np.median(np.abs(window_data - median))
            if mad == 0:
                continue
            modified_z = 0.6745 * (arr[i] - median) / mad
            if abs(modified_z) > self.threshold:
                anomalies.append({
                    "index": i,
                    "value": float(arr[i]),
                    "baseline": float(median),
                    "z_score": float(abs(modified_z)),
                    "method": "rolling_mad",
                    "severity": "critical" if abs(modified_z) > 6 else "warning",
                })

        return anomalies

    def isolation_forest_detect(self, values: list[float]) -> list[dict]:
        """Isolation Forest anomaliya aşkarlaması."""
        if len(values) < 20:
            return []

        arr = np.array(values).reshape(-1, 1)
        self.iso_forest.fit(arr)
        predictions = self.iso_forest.predict(arr)
        scores = self.iso_forest.decision_function(arr)

        anomalies = []
        for i, (pred, score) in enumerate(zip(predictions, scores)):
            if pred == -1:
                anomalies.append({
                    "index": i,
                    "value": float(values[i]),
                    "anomaly_score": float(-score),
                    "method": "isolation_forest",
                    "severity": "critical" if score < -0.3 else "warning",
                })

        return anomalies

    def detect(self, bank_id: str, latency_series: list[float]) -> dict:
        """Hər iki metodu tətbiq et, nəticəni birləşdir."""
        mad_anomalies = self.rolling_mad_detect(latency_series)
        iso_anomalies = self.isolation_forest_detect(latency_series)

        # İndeks üzrə birləşdir
        iso_indices = {a["index"] for a in iso_anomalies}
        mad_indices = {a["index"] for a in mad_anomalies}
        consensus = iso_indices & mad_indices  # Hər iki metod razıdır

        all_anomalies = []
        seen = set()
        for a in mad_anomalies + iso_anomalies:
            if a["index"] not in seen:
                a["consensus"] = a["index"] in consensus
                a["bank_id"] = bank_id
                all_anomalies.append(a)
                seen.add(a["index"])

        return {
            "bank_id": bank_id,
            "total_points": len(latency_series),
            "anomaly_count": len(seen),
            "consensus_anomalies": len(consensus),
            "anomalies": sorted(all_anomalies, key=lambda x: x["index"]),
        }


# ─── A9: Qiymətləndirmə Dəsti ────────────────────────────────────────────────

def evaluate_anomaly_detection(detector: AnomalyDetector) -> dict:
    """
    Məlum etiketlənmiş məlumatla aşkarlama keyfiyyətini ölç.
    Pitch üçün rəqəmlər.
    """
    results = {"bank_metrics": {}}

    for bank_id in BANK_PROFILES:
        data = generate_synthetic_telemetry(bank_id, n_points=200)
        latencies = [d["latency_ms"] for d in data]
        true_anomaly_indices = {i for i, d in enumerate(data) if d["label"] != "normal"}

        detection = detector.detect(bank_id, latencies)
        detected_indices = {a["index"] for a in detection["anomalies"]}

        # Metriklər
        tp = len(true_anomaly_indices & detected_indices)
        fp = len(detected_indices - true_anomaly_indices)
        fn = len(true_anomaly_indices - detected_indices)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        results["bank_metrics"][bank_id] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1_score": round(f1, 3),
            "true_anomalies": len(true_anomaly_indices),
            "detected": len(detected_indices),
            "true_positives": tp,
        }

    # Orta göstəricilər
    all_p = [m["precision"] for m in results["bank_metrics"].values()]
    all_r = [m["recall"] for m in results["bank_metrics"].values()]
    results["overall"] = {
        "avg_precision": round(sum(all_p) / len(all_p), 3),
        "avg_recall": round(sum(all_r) / len(all_r), 3),
        "detection_latency_estimate_ms": "<500",
    }

    return results


# ─── Əsas Loop ────────────────────────────────────────────────────────────────

detector = AnomalyDetector()


async def run_anomaly_scan():
    """Hər 10 dəqiqədə latency anomaliyalarını yoxla."""
    global pool
    if not pool:
        return

    try:
        for bank_id in BANK_PROFILES:
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT p95 FROM latency_metrics
                    WHERE bank_id = $1
                    ORDER BY measured_at DESC
                    LIMIT 100
                """, bank_id)

            if len(rows) < 10:
                continue

            latencies = [float(r["p95"]) for r in reversed(rows)]
            result = detector.detect(bank_id, latencies)

            for anomaly in result["anomalies"]:
                if anomaly.get("severity") in ("critical", "warning"):
                    async with pool.acquire() as conn:
                        await conn.execute("""
                            INSERT INTO anomalies
                                (bank_id, anomaly_type, severity, metric_value, baseline_value, deviation_factor)
                            VALUES ($1, $2, $3, $4, $5, $6)
                            ON CONFLICT DO NOTHING
                        """,
                            bank_id,
                            "latency_spike",
                            anomaly["severity"],
                            anomaly["value"],
                            anomaly.get("baseline", 0),
                            anomaly.get("z_score", 0),
                        )

            if redis_client:
                await redis_client.setex(
                    f"anomaly_scan:{bank_id}",
                    600,
                    json.dumps(result, default=str),
                )

        print(f"[AI] Anomaliya skanı tamamlandı — {datetime.now(timezone.utc).isoformat()}")
    except Exception as e:
        print(f"[AI] Xəta: {e}")


async def run_evaluation():
    """Qiymətləndirmə dəstini icra et və nəticəni yaz."""
    print("[AI] Qiymətləndirmə dəsti işə salınır...")
    results = evaluate_anomaly_detection(detector)
    print(f"[AI] Nəticələr: {json.dumps(results, indent=2)}")

    if redis_client:
        await redis_client.setex("evaluation_results", 3600, json.dumps(results))

    print(f"[AI] Qiymətləndirmə tamamlandı — Ort. Dəqiqlik: {results['overall']['avg_precision']:.1%}, "
          f"Ort. Tam aşkarlama: {results['overall']['avg_recall']:.1%}")


async def main():
    global pool, redis_client

    await asyncio.sleep(15)  # Backend-in tam işə düşməsini gözlə

    print("[AI] Mühərrik başladı...")
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    redis_client = await aioredis.from_url(REDIS_URL, decode_responses=True)

    scheduler.add_job(run_anomaly_scan, "interval", minutes=10, id="anomaly_scan")
    scheduler.start()

    # İlk qiymətləndirməni dərhal icra et
    await run_evaluation()
    await run_anomaly_scan()

    print("[AI] Mühərrik aktiv. Növbəti skan: 10 dəqiqə sonra.")

    # Sonsuz gözləmə
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
