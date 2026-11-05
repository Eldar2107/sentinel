"""
Sentinel — Əsas Backend API
FastAPI + APScheduler + PostgreSQL + Redis
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from core.compliance import checker as compliance_checker
from core.drift import drift_detector
from core.security import scanner as security_scanner
from core.normalization import normalizer
from core.scoring import calculate_bank_score
from core.database import db

# ─── Konfiqurasiya ───────────────────────────────────────────────────────────
BANKS = {
    "bank_a": {"name": "TBC Bank (Compliant)", "url": os.getenv("BANK_A_URL", "http://bank-a:8000")},
    "bank_b": {"name": "Bank of Georgia (Drift)", "url": os.getenv("BANK_B_URL", "http://bank-b:8000")},
    "bank_c": {"name": "Liberty Bank (Unstable)", "url": os.getenv("BANK_C_URL", "http://bank-c:8000")},
}

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

TEST_SCENARIOS = [
    {"id": 1, "name": "Get Account List", "category": "accounts",
     "endpoint": "/v1/accounts", "method": "GET", "expected_status": 200},
    {"id": 2, "name": "Get Single Account", "category": "accounts",
     "endpoint": "/v1/accounts/acc-001", "method": "GET", "expected_status": 200},
    {"id": 3, "name": "Get Balances", "category": "balances",
     "endpoint": "/v1/accounts/acc-001/balances", "method": "GET", "expected_status": 200},
    {"id": 4, "name": "Get Transactions", "category": "transactions",
     "endpoint": "/v1/accounts/acc-001/transactions", "method": "GET", "expected_status": 200},
    {"id": 5, "name": "Initiate Payment", "category": "payments",
     "endpoint": "/v1/payments/sepa-credit-transfers", "method": "POST",
     "expected_status": 201,
     "body": {
         "creditorAccount": {"iban": "GE29NB0000000101904917"},
         "instructedAmount": {"amount": "100.00", "currency": "GEL"},
         "creditorName": "Test Merchant",
         "debtorAccount": {"iban": "GE80TB7241336080100003"},
     }},
    {"id": 6, "name": "Create Consent", "category": "consent",
     "endpoint": "/v1/consents", "method": "POST",
     "expected_status": 201,
     "body": {
         "access": {"accounts": [], "balances": [], "transactions": []},
         "recurringIndicator": False,
         "validUntil": "2025-12-31",
         "frequencyPerDay": 4,
     }},
]

app = FastAPI(title="Sentinel API", version="2.0.0", description="Georgia Open Banking Monitor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = AsyncIOScheduler()
redis_client: Optional[aioredis.Redis] = None


# ─── Startup ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    global redis_client
    await db.connect()
    redis_client = await aioredis.from_url(REDIS_URL, decode_responses=True)
    scheduler.add_job(run_all_tests, "interval", minutes=5, id="periodic_tests")
    scheduler.add_job(run_uptime_checks, "interval", minutes=2, id="uptime_checks")
    scheduler.start()
    # İlk test dərhal icra et
    asyncio.create_task(run_all_tests())


@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()
    await db.disconnect()
    if redis_client:
        await redis_client.close()


# ─── Yardımçı Funksiyalar ────────────────────────────────────────────────────

async def call_bank(bank_id: str, method: str, path: str, body: dict = None) -> dict:
    """Bank API-sinə çağırış et."""
    bank = BANKS[bank_id]
    url = f"{bank['url']}{path}"
    
    headers = {"X-Request-ID": f"sentinel-{int(time.time())}"}
    if bank_id == "bank_c":
        headers["X-Liberty-API-Key"] = "sentinel-test-key"

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            if method == "GET":
                resp = await client.get(url, headers=headers)
            elif method == "POST":
                resp = await client.post(url, json=body or {}, headers=headers)
            else:
                resp = await client.request(method, url, headers=headers)

            latency_ms = (time.monotonic() - start) * 1000
            try:
                resp_body = resp.json()
            except Exception:
                resp_body = {"raw": resp.text}

            return {
                "status_code": resp.status_code,
                "body": resp_body,
                "headers": dict(resp.headers),
                "latency_ms": latency_ms,
                "error": None,
            }
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            return {
                "status_code": 0,
                "body": {},
                "headers": {},
                "latency_ms": latency_ms,
                "error": str(e),
            }


async def run_all_tests():
    """Bütün banklar üçün bütün test ssenariləri icra et."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Test tsikli başladı...")
    latency_results = {bank_id: [] for bank_id in BANKS}

    for bank_id in BANKS:
        bank_results = []
        baseline_snapshots = {}

        for scenario in TEST_SCENARIOS:
            result = await call_bank(
                bank_id,
                scenario["method"],
                scenario["endpoint"],
                scenario.get("body"),
            )

            # Uyğunluq yoxla
            compliance = compliance_checker.check_response(
                scenario["category"],
                result["status_code"],
                result["body"],
                result["headers"],
            )

            # Drift yoxla
            snap_key = f"{bank_id}:{scenario['endpoint']}"
            drift_events = []
            if result["status_code"] == 200 and result["body"]:
                current_fp = drift_detector.fingerprint_hash(result["body"])
                if snap_key in baseline_snapshots:
                    old_body = baseline_snapshots[snap_key]
                    diffs = drift_detector.compare(old_body, result["body"])
                    if diffs:
                        drift_events = diffs
                        await save_drift_events(bank_id, scenario["endpoint"], diffs)
                baseline_snapshots[snap_key] = result["body"]

            # Təhlükəsizlik skanı
            sec_result = security_scanner.full_scan(
                bank_id, result["headers"], result["body"],
                scenario["category"] if scenario["category"] in ("payments", "consent") else None,
            )

            # Normalizasiya
            normalized = None
            if result["status_code"] in (200, 201) and result["body"]:
                try:
                    cat = scenario["category"]
                    if cat == "accounts":
                        normalized = normalizer.normalize_account_list(result["body"], bank_id)
                    elif cat == "balances":
                        normalized = normalizer.normalize_balance_list(result["body"], bank_id)
                    elif cat == "transactions":
                        normalized = normalizer.normalize_transaction_list(result["body"], bank_id)
                    elif cat == "payments":
                        normalized = normalizer.normalize_payment_response(result["body"], bank_id)
                except Exception as e:
                    normalized = {"error": str(e)}

            test_result = {
                "bank_id": bank_id,
                "scenario": scenario["name"],
                "category": scenario["category"],
                "endpoint": scenario["endpoint"],
                "method": scenario["method"],
                "status_code": result["status_code"],
                "latency_ms": result["latency_ms"],
                "is_compliant": compliance["is_compliant"],
                "compliance_score": compliance["score"],
                "compliance_issues": compliance["issues"],
                "security_score": sec_result["overall_score"],
                "security_issues": sec_result["all_issues"],
                "drift_events": drift_events,
                "normalized": normalized,
                "error": result["error"],
            }

            bank_results.append(test_result)
            latency_results[bank_id].append(result["latency_ms"])

            # DB-ə yaz
            await db.save_test_result(test_result)

        # Latency metriklər
        lats = sorted([l for l in latency_results[bank_id] if l > 0])
        if lats:
            n = len(lats)
            p50 = lats[int(n * 0.50)]
            p95 = lats[int(n * 0.95)] if n > 1 else lats[-1]
            p99 = lats[int(n * 0.99)] if n > 1 else lats[-1]
            await db.save_latency_metrics(bank_id, p50, p95, p99)

        # Skor hesabla
        score = await calculate_bank_score(bank_id, bank_results, db)
        await db.save_bank_score(bank_id, score)

        # Redis-ə keşlə
        if redis_client:
            await redis_client.setex(
                f"latest_results:{bank_id}",
                300,
                json.dumps(bank_results, default=str),
            )
            await redis_client.setex(
                f"bank_score:{bank_id}",
                300,
                json.dumps(score, default=str),
            )

    print(f"[{datetime.now(timezone.utc).isoformat()}] Test tsikli tamamlandı.")


async def run_uptime_checks():
    """Uptime monitorinq."""
    for bank_id in BANKS:
        result = await call_bank(bank_id, "GET", "/health")
        is_up = result["status_code"] == 200 and result["error"] is None
        await db.save_uptime(bank_id, is_up, result["status_code"], result["error"])


async def save_drift_events(bank_id: str, endpoint: str, diffs: list):
    """Drift hadisələrini DB-ə yaz."""
    for diff in diffs:
        await db.save_drift_event(bank_id, endpoint, diff)


# ─── REST API Endpointləri ───────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(), "version": "2.0.0"}


@app.get("/api/banks")
async def get_banks():
    banks_out = []
    for bank_id, info in BANKS.items():
        score_data = None
        if redis_client:
            cached = await redis_client.get(f"bank_score:{bank_id}")
            if cached:
                score_data = json.loads(cached)
        if not score_data:
            score_data = await db.get_latest_score(bank_id)
        banks_out.append({
            "id": bank_id,
            "name": info["name"],
            "score": score_data,
        })
    return {"banks": banks_out}


@app.get("/api/banks/{bank_id}/results")
async def get_bank_results(bank_id: str, limit: int = 50):
    if bank_id not in BANKS:
        raise HTTPException(status_code=404, detail="Bank tapılmadı")
    
    if redis_client:
        cached = await redis_client.get(f"latest_results:{bank_id}")
        if cached:
            return {"bank_id": bank_id, "results": json.loads(cached)}

    results = await db.get_test_results(bank_id, limit)
    return {"bank_id": bank_id, "results": results}


@app.get("/api/banks/{bank_id}/latency")
async def get_latency(bank_id: str, hours: int = 24):
    if bank_id not in BANKS:
        raise HTTPException(status_code=404, detail="Bank tapılmadı")
    metrics = await db.get_latency_history(bank_id, hours)
    return {"bank_id": bank_id, "metrics": metrics}


@app.get("/api/banks/{bank_id}/uptime")
async def get_uptime(bank_id: str, hours: int = 24):
    if bank_id not in BANKS:
        raise HTTPException(status_code=404, detail="Bank tapılmadı")
    records = await db.get_uptime_history(bank_id, hours)
    total = len(records)
    up = sum(1 for r in records if r.get("is_up"))
    pct = (up / total * 100) if total > 0 else 0
    return {"bank_id": bank_id, "uptime_pct": round(pct, 2), "records": records}


@app.get("/api/drift")
async def get_drift_events(bank_id: str = None, limit: int = 50):
    events = await db.get_drift_events(bank_id, limit)
    return {"events": events}


@app.get("/api/anomalies")
async def get_anomalies(bank_id: str = None):
    anomalies = await db.get_anomalies(bank_id)
    return {"anomalies": anomalies}


@app.get("/api/scores")
async def get_all_scores():
    scores = {}
    for bank_id in BANKS:
        scores[bank_id] = await db.get_latest_score(bank_id)
    return {"scores": scores, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/api/run-tests")
async def trigger_tests(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_all_tests)
    return {"message": "Test ssenariləri başladıldı", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/dashboard")
async def get_dashboard_data():
    """Dashboard üçün bütün məlumatları bir endpointdə topla."""
    dashboard = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "banks": {},
    }

    for bank_id, info in BANKS.items():
        # Skor
        score_data = None
        if redis_client:
            cached = await redis_client.get(f"bank_score:{bank_id}")
            if cached:
                score_data = json.loads(cached)
        if not score_data:
            score_data = await db.get_latest_score(bank_id)

        # Latency (son)
        latency = await db.get_latest_latency(bank_id)

        # Uptime (son 24h)
        uptime_records = await db.get_uptime_history(bank_id, 24)
        total = len(uptime_records)
        up = sum(1 for r in uptime_records if r.get("is_up"))
        uptime_pct = (up / total * 100) if total > 0 else 100.0

        # Drift (son)
        drift = await db.get_drift_events(bank_id, 5)

        dashboard["banks"][bank_id] = {
            "name": info["name"],
            "score": score_data,
            "latency": latency,
            "uptime_pct": round(uptime_pct, 2),
            "recent_drift": drift,
            "anomalies": await db.get_anomalies(bank_id, limit=5),
        }

    dashboard["recent_anomalies"] = await db.get_anomalies(limit=15)
    return dashboard


@app.get("/api/report/{bank_id}")
async def get_text_report(bank_id: str):
    """Sadə dildə hesabat generatoru (A8)."""
    if bank_id not in BANKS:
        raise HTTPException(status_code=404, detail="Bank tapılmadı")

    score_data = await db.get_latest_score(bank_id)
    latency = await db.get_latest_latency(bank_id)
    drift_events = await db.get_drift_events(bank_id, 10)

    report = generate_text_report(bank_id, BANKS[bank_id]["name"], score_data, latency, drift_events)
    return {"bank_id": bank_id, "report": report}


def generate_text_report(bank_id: str, bank_name: str, score: dict, latency: dict, drifts: list) -> str:
    """Qeyri-texniki dildə hesabat mətni (A8)."""
    if not score:
        return f"{bank_name} üçün hələ məlumat yoxdur. Testlər davam edir."

    total = score.get("total_score", 0)
    grade = "A" if total >= 90 else "B" if total >= 75 else "C" if total >= 60 else "D"

    lines = [
        f"# {bank_name} — Texniki Uyğunluq Hesabatı",
        f"**Ümumi Bal:** {total:.1f}/100 (Qiymət: {grade})",
        "",
        "## Əsas Göstəricilər",
    ]

    breakdown = score.get("score_breakdown", {})
    lines.append(f"- **Standart Uyğunluğu:** {breakdown.get('compliance', 0):.1f}/100")
    lines.append(f"- **Xidmət Etibarlılığı:** {breakdown.get('reliability', 0):.1f}/100")
    lines.append(f"- **Cavab Sürəti:** {breakdown.get('latency', 0):.1f}/100")
    lines.append(f"- **Kibertəhlükəsizlik:** {breakdown.get('security', 0):.1f}/100")

    if latency:
        lines.append("")
        lines.append("## Cavab Vaxtı")
        lines.append(f"- Mediana (p50): {latency.get('p50', 0):.0f}ms")
        lines.append(f"- Yüksək yük (p95): {latency.get('p95', 0):.0f}ms")
        lines.append(f"- Kritik yük (p99): {latency.get('p99', 0):.0f}ms")

    if drifts:
        lines.append("")
        lines.append(f"## Struktur Dəyişiklikləri ({len(drifts)} hadisə)")
        for d in drifts[:3]:
            lines.append(f"- **{d.get('drift_type', 'Naməlum')}**: {d.get('field_path', '')} sahəsi — {d.get('description', '')}")

    if total < 60:
        lines.append("")
        lines.append("> ⚠️ Bu bankın performansı narahatçılıq doğurur. Tənzimləyici orqana məlumat verilməsi tövsiyə olunur.")
    elif total < 80:
        lines.append("")
        lines.append("> ℹ️ Bəzi sahələrdə təkmilləşmə lazımdır.")
    else:
        lines.append("")
        lines.append("> ✅ Bank standartlara ümumi olaraq uyğundur.")

    return "\n".join(lines)
