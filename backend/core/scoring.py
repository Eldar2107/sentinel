"""
Sentinel — Scoring Engine (A2)
İzah olunan 0-100 bal sistemi.
"""

import math
from typing import Optional


async def calculate_bank_score(bank_id: str, test_results: list, db) -> dict:
    """
    Ağırlıqlı skor hesabla:
      Compliance  35%
      Reliability 25%
      Latency     20%
      Security    20%
    """
    if not test_results:
        return _empty_score(bank_id)

    # ── Compliance ────────────────────────────────────────────────────────────
    compliance_scores = [r["compliance_score"] for r in test_results if r.get("compliance_score") is not None]
    compliance = sum(compliance_scores) / len(compliance_scores) if compliance_scores else 0

    # ── Reliability ───────────────────────────────────────────────────────────
    total_calls = len(test_results)
    failed_calls = sum(1 for r in test_results if r.get("error") or r.get("status_code", 0) >= 500)
    error_rate = failed_calls / total_calls if total_calls > 0 else 0
    reliability = max(0, 100 - (error_rate * 100) * 2)  # hər 1% xəta → -2 bal

    # ── Latency ───────────────────────────────────────────────────────────────
    latencies = [r["latency_ms"] for r in test_results if r.get("latency_ms", 0) > 0]
    if latencies:
        latencies_sorted = sorted(latencies)
        n = len(latencies_sorted)
        p95 = latencies_sorted[min(int(n * 0.95), n - 1)]
        latency_score = _latency_to_score(p95)
    else:
        latency_score = 50.0

    # ── Security ──────────────────────────────────────────────────────────────
    sec_scores = [r["security_score"] for r in test_results if r.get("security_score") is not None]
    security = sum(sec_scores) / len(sec_scores) if sec_scores else 50.0

    # ── Ağırlıqlı cəm ────────────────────────────────────────────────────────
    total = (
        compliance * 0.35
        + reliability * 0.25
        + latency_score * 0.20
        + security * 0.20
    )

    # ── Açıqlama ──────────────────────────────────────────────────────────────
    reasons = _build_reasons(compliance, reliability, latency_score, security, latencies)

    return {
        "bank_id": bank_id,
        "total_score": round(total, 1),
        "compliance_score": round(compliance, 1),
        "reliability_score": round(reliability, 1),
        "latency_score": round(latency_score, 1),
        "security_score": round(security, 1),
        "score_breakdown": {
            "compliance": round(compliance, 1),
            "reliability": round(reliability, 1),
            "latency": round(latency_score, 1),
            "security": round(security, 1),
        },
        "reasons": reasons,
        "grade": _to_grade(total),
    }


def _latency_to_score(p95_ms: float) -> float:
    """p95 gecikmə → skor. Aşağı gecikmə = yüksək bal."""
    if p95_ms <= 200:
        return 100.0
    elif p95_ms <= 400:
        return 90.0 - (p95_ms - 200) * 0.10
    elif p95_ms <= 800:
        return 70.0 - (p95_ms - 400) * 0.10
    elif p95_ms <= 1500:
        return 30.0 - (p95_ms - 800) * 0.02
    return 0.0


def _to_grade(score: float) -> str:
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B+"
    elif score >= 70:
        return "B"
    elif score >= 60:
        return "C"
    elif score >= 50:
        return "D"
    return "F"


def _build_reasons(compliance: float, reliability: float, latency: float, security: float, latencies: list) -> list:
    """Balın niyə kəsildiyini açıqlayan səbəb siyahısı."""
    reasons = []

    if compliance < 90:
        deduction = 100 - compliance
        reasons.append({
            "category": "compliance",
            "impact": round(-deduction * 0.35, 1),
            "message": f"Berlin Group uyğunluq balı {compliance:.0f}/100 — standart sahələr, format və ya status kodlarında sapma var",
        })

    if reliability < 95:
        deduction = 100 - reliability
        reasons.append({
            "category": "reliability",
            "impact": round(-deduction * 0.25, 1),
            "message": f"Etibarlılıq {reliability:.0f}/100 — xəta nisbəti yüksəkdir",
        })

    if latency < 80 and latencies:
        sorted_l = sorted(latencies)
        n = len(sorted_l)
        p95 = sorted_l[min(int(n * 0.95), n - 1)]
        reasons.append({
            "category": "latency",
            "impact": round(-(100 - latency) * 0.20, 1),
            "message": f"p95 gecikmə {p95:.0f}ms — PSD2 tövsiyə həddi olan 500ms-dən yüksəkdir",
        })

    if security < 80:
        reasons.append({
            "category": "security",
            "impact": round(-(100 - security) * 0.20, 1),
            "message": f"Təhlükəsizlik balı {security:.0f}/100 — TLS versiyası, başlıqlar və ya SCA axınında problem var",
        })

    if not reasons:
        reasons.append({
            "category": "overall",
            "impact": 0,
            "message": "Bütün göstəricilər qənaətbəxş səviyyədədir",
        })

    return reasons


def _empty_score(bank_id: str) -> dict:
    return {
        "bank_id": bank_id,
        "total_score": 0,
        "compliance_score": 0,
        "reliability_score": 0,
        "latency_score": 0,
        "security_score": 0,
        "score_breakdown": {"compliance": 0, "reliability": 0, "latency": 0, "security": 0},
        "reasons": [{"category": "overall", "impact": 0, "message": "Hələ məlumat yoxdur"}],
        "grade": "N/A",
    }
