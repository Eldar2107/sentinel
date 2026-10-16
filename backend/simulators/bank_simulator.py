"""
Sentinel — Bank Simulator
Hər bank öz davranış profiliylə işləyir.
Mühit dəyişənlərindən konfiqurasiya olunur.
"""

import asyncio
import os
import random
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ─── Konfiqurasiya ───────────────────────────────────────────────────────────
BANK_ID = os.getenv("BANK_ID", "bank_a")
BANK_NAME = os.getenv("BANK_NAME", "Demo Bank")
BASE_LATENCY_MS = int(os.getenv("LATENCY_MS", "120"))
ERROR_RATE = float(os.getenv("ERROR_RATE", "0.01"))
DATE_FORMAT = os.getenv("DATE_FORMAT", "iso8601")   # iso8601 | slash | unix
SCHEMA_STRICT = os.getenv("SCHEMA_STRICT", "true").lower() == "true"
EXTRA_FIELDS = os.getenv("EXTRA_FIELDS", "false").lower() == "true"
REQUIRE_CUSTOM_HEADER = os.getenv("REQUIRE_CUSTOM_HEADER", "false").lower() == "true"
FLAKY = os.getenv("FLAKY", "false").lower() == "true"

app = FastAPI(title=f"Sentinel Simulator — {BANK_NAME}", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Yardımçı funksiyalar ────────────────────────────────────────────────────

def format_date(dt: datetime) -> Any:
    """Bank-spesifik tarix formatı."""
    if DATE_FORMAT == "iso8601":
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    elif DATE_FORMAT == "slash":
        return dt.strftime("%Y/%m/%d %H:%M:%S")
    elif DATE_FORMAT == "unix":
        return int(dt.timestamp())
    return dt.isoformat()


def make_amount(value: float, currency: str = "GEL") -> dict:
    """Berlin Group Amount obyekti."""
    if SCHEMA_STRICT:
        return {"amount": f"{value:.2f}", "currency": currency}
    else:
        # Non-compliant: float əvəzinə int və ya fərqli quruluş
        return {"value": value, "ccy": currency}


def inject_latency():
    """Bank-ın gecikmə profilinə uyğun gözləmə."""
    jitter = random.gauss(0, BASE_LATENCY_MS * 0.15)
    latency = max(10, BASE_LATENCY_MS + jitter) / 1000
    if FLAKY and random.random() < 0.12:
        latency += random.uniform(1.5, 4.0)   # spike
    time.sleep(latency)


def maybe_error():
    """Stoxastik xəta simulyasiyası."""
    if random.random() < ERROR_RATE:
        codes = [500, 502, 503, 504] if FLAKY else [500]
        raise HTTPException(
            status_code=random.choice(codes),
            detail=build_error("SERVER_ERROR", "Internal server error occurred"),
        )


def build_error(code: str, message: str) -> dict:
    """Berlin Group uyğun xəta quruluşu."""
    if SCHEMA_STRICT:
        return {
            "tppMessages": [
                {"category": "ERROR", "code": code, "text": message}
            ]
        }
    else:
        return {"error": code, "message": message}


# ─── Saxta Məlumatlar ────────────────────────────────────────────────────────

ACCOUNTS = [
    {
        "resourceId": "acc-001",
        "iban": "GE29NB0000000101904917",
        "name": "Levan Beridze",
        "currency": "GEL",
        "product": "Current Account",
        "status": "enabled",
    },
    {
        "resourceId": "acc-002",
        "iban": "GE80TB7241336080100003",
        "name": "Nino Kvaratskhelia",
        "currency": "USD",
        "product": "Savings Account",
        "status": "enabled",
    },
    {
        "resourceId": "acc-003",
        "iban": "GE57LB0113113080179081",
        "name": "Giorgi Tabatadze",
        "currency": "EUR",
        "product": "Business Account",
        "status": "enabled",
    },
]

TRANSACTIONS = [
    {
        "transactionId": "txn-1001",
        "creditorName": "Tbilisi Parking",
        "transactionAmount": 15.0,
        "currency": "GEL",
        "bookingDate": datetime(2024, 10, 1, 9, 0, 0, tzinfo=timezone.utc),
        "valueDate": datetime(2024, 10, 1, 9, 0, 0, tzinfo=timezone.utc),
        "remittanceInformationUnstructured": "Parking fee",
        "creditDebitIndicator": "DBIT",
        "status": "Booked",
    },
    {
        "transactionId": "txn-1002",
        "creditorName": "Carrefour",
        "transactionAmount": 87.50,
        "currency": "GEL",
        "bookingDate": datetime(2024, 10, 2, 14, 23, 0, tzinfo=timezone.utc),
        "valueDate": datetime(2024, 10, 2, 14, 23, 0, tzinfo=timezone.utc),
        "remittanceInformationUnstructured": "Grocery shopping",
        "creditDebitIndicator": "DBIT",
        "status": "Booked",
    },
    {
        "transactionId": "txn-1003",
        "creditorName": "Salary Transfer",
        "transactionAmount": 3200.0,
        "currency": "GEL",
        "bookingDate": datetime(2024, 10, 3, 8, 0, 0, tzinfo=timezone.utc),
        "valueDate": datetime(2024, 10, 3, 8, 0, 0, tzinfo=timezone.utc),
        "remittanceInformationUnstructured": "October salary",
        "creditDebitIndicator": "CRDT",
        "status": "Booked",
    },
]


def build_account(acc: dict) -> dict:
    """Cavab strukturunu bank-a uyğun formatla."""
    base = {
        "resourceId": acc["resourceId"],
        "iban": acc["iban"],
        "currency": acc["currency"],
        "name": acc["name"],
        "product": acc["product"],
        "status": acc["status"],
        "links": {
            "self": {"href": f"/v1/accounts/{acc['resourceId']}"},
            "balances": {"href": f"/v1/accounts/{acc['resourceId']}/balances"},
            "transactions": {"href": f"/v1/accounts/{acc['resourceId']}/transactions"},
        }
    }
    if not SCHEMA_STRICT:
        # Bank B: "links" → "href" strukturu fərqli
        base["_links"] = base.pop("links")
    if EXTRA_FIELDS:
        base["internalCode"] = f"INT-{acc['resourceId'].upper()}"
        base["branchCode"] = "TBS-001"
    return base


def build_transaction(txn: dict) -> dict:
    """Tranzaksiya obyektini bank-a uyğun formatla."""
    base: dict = {
        "transactionId": txn["transactionId"],
        "transactionAmount": make_amount(txn["transactionAmount"], txn["currency"]),
        "bookingDate": format_date(txn["bookingDate"]),
        "valueDate": format_date(txn["valueDate"]),
        "remittanceInformationUnstructured": txn["remittanceInformationUnstructured"],
        "creditorName": txn["creditorName"],
        "creditDebitIndicator": txn["creditDebitIndicator"],
    }
    if SCHEMA_STRICT:
        base["status"] = txn["status"]
    else:
        base["txnStatus"] = txn["status"]  # Non-standard field name

    if EXTRA_FIELDS:
        base["processingCode"] = f"PC-{random.randint(1000, 9999)}"
    return base


# ─── Middleware: Custom Header Yoxlaması ─────────────────────────────────────

@app.middleware("http")
async def check_custom_header(request: Request, call_next):
    if REQUIRE_CUSTOM_HEADER and request.url.path.startswith("/v1/"):
        if "X-Liberty-API-Key" not in request.headers:
            return JSONResponse(
                status_code=401,
                content=build_error("MISSING_HEADER", "X-Liberty-API-Key header required"),
            )
    response = await call_next(request)
    response.headers["X-Bank-ID"] = BANK_ID
    response.headers["X-Content-Type-Options"] = "nosniff"
    if SCHEMA_STRICT:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


# ─── Endpointlər ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "up", "bank": BANK_ID, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/v1/accounts")
async def get_accounts():
    inject_latency()
    maybe_error()
    accounts = [build_account(a) for a in ACCOUNTS]
    if SCHEMA_STRICT:
        return {"accounts": accounts}
    else:
        return {"data": accounts, "page": 1, "total": len(accounts)}


@app.get("/v1/accounts/{account_id}")
async def get_account(account_id: str):
    inject_latency()
    maybe_error()
    acc = next((a for a in ACCOUNTS if a["resourceId"] == account_id), None)
    if not acc:
        raise HTTPException(status_code=404, detail=build_error("NOT_FOUND", "Account not found"))
    return build_account(acc)


@app.get("/v1/accounts/{account_id}/balances")
async def get_balances(account_id: str):
    inject_latency()
    maybe_error()
    acc = next((a for a in ACCOUNTS if a["resourceId"] == account_id), None)
    if not acc:
        raise HTTPException(status_code=404, detail=build_error("NOT_FOUND", "Account not found"))

    base_amount = round(random.uniform(500, 15000), 2)
    balances = [
        {
            "balanceType": "closingBooked",
            "balanceAmount": make_amount(base_amount, acc["currency"]),
            "referenceDate": format_date(datetime.now(timezone.utc)),
            "lastChangeDateTime": format_date(datetime.now(timezone.utc)),
        },
        {
            "balanceType": "expected",
            "balanceAmount": make_amount(base_amount - random.uniform(0, 500), acc["currency"]),
            "referenceDate": format_date(datetime.now(timezone.utc)),
            "lastChangeDateTime": format_date(datetime.now(timezone.utc)),
        },
    ]
    if SCHEMA_STRICT:
        return {"balances": balances, "account": {"iban": acc["iban"]}}
    else:
        return {"balance_list": balances}


@app.get("/v1/accounts/{account_id}/transactions")
async def get_transactions(account_id: str, dateFrom: str = None, dateTo: str = None):
    inject_latency()
    maybe_error()
    acc = next((a for a in ACCOUNTS if a["resourceId"] == account_id), None)
    if not acc:
        raise HTTPException(status_code=404, detail=build_error("NOT_FOUND", "Account not found"))

    txns = [build_transaction(t) for t in TRANSACTIONS]
    if SCHEMA_STRICT:
        return {
            "transactions": {
                "booked": txns,
                "pending": [],
            },
            "account": {"iban": acc["iban"]},
        }
    else:
        return {"transactionList": txns, "status": "success"}


@app.post("/v1/payments/sepa-credit-transfers")
async def initiate_payment(request: Request):
    inject_latency()
    maybe_error()
    body = await request.json()

    # Məcburi sahələrin yoxlanması
    required = ["creditorAccount", "instructedAmount", "creditorName"]
    missing = [f for f in required if f not in body]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=build_error("FORMAT_ERROR", f"Missing fields: {', '.join(missing)}"),
        )

    payment_id = f"pmt-{uuid.uuid4().hex[:8]}"
    if SCHEMA_STRICT:
        return {
            "paymentId": payment_id,
            "transactionStatus": "RCVD",
            "_links": {
                "scaRedirect": {"href": f"https://sandbox.bank.ge/sca/{payment_id}"},
                "self": {"href": f"/v1/payments/sepa-credit-transfers/{payment_id}"},
            }
        }
    else:
        return {
            "id": payment_id,
            "status": "received",
            "sca_url": f"https://sandbox.bank.ge/auth/{payment_id}",
        }


@app.get("/v1/payments/sepa-credit-transfers/{payment_id}/status")
async def get_payment_status(payment_id: str):
    inject_latency()
    maybe_error()
    statuses = ["RCVD", "ACTC", "ACSC", "RJCT"] if SCHEMA_STRICT else ["received", "processing", "completed", "rejected"]
    return {
        ("transactionStatus" if SCHEMA_STRICT else "status"): random.choice(statuses[:3]),
        "paymentId" if SCHEMA_STRICT else "id": payment_id,
    }


@app.post("/v1/consents")
async def create_consent(request: Request):
    inject_latency()
    maybe_error()
    body = await request.json()
    consent_id = f"cns-{uuid.uuid4().hex[:8]}"

    if SCHEMA_STRICT:
        return {
            "consentId": consent_id,
            "consentStatus": "received",
            "_links": {
                "scaRedirect": {"href": f"https://sandbox.bank.ge/consent/{consent_id}"},
                "self": {"href": f"/v1/consents/{consent_id}"},
            }
        }
    else:
        return {
            "consent_id": consent_id,
            "state": "pending",
            "redirect": f"https://sandbox.bank.ge/consent/{consent_id}",
        }


@app.get("/v1/consents/{consent_id}/status")
async def get_consent_status(consent_id: str):
    inject_latency()
    maybe_error()
    return {
        "consentId" if SCHEMA_STRICT else "consent_id": consent_id,
        "consentStatus" if SCHEMA_STRICT else "status": "valid",
    }
