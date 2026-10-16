"""
Sentinel — Normalizasiya Qatı (B10)
Fərqli bank cavablarını vahid standart formata çevirir.
"""

from typing import Any, Optional
import re
from datetime import datetime


class NormalizationLayer:
    """
    Müxtəlif bank formatlarından gələn cavabları
    Berlin Group NextGenPSD2-yə uyğun vahid formata çevirir.
    """

    def normalize_account_list(self, raw: Any, bank_id: str) -> dict:
        """Hesab siyahısını normalize et."""
        accounts = []
        
        # Fərqli quruluşları tanı
        if isinstance(raw, dict):
            if "accounts" in raw:
                raw_accounts = raw["accounts"]
            elif "data" in raw:
                raw_accounts = raw["data"]
            elif isinstance(raw.get("accounts"), list):
                raw_accounts = raw["accounts"]
            else:
                raw_accounts = []
        elif isinstance(raw, list):
            raw_accounts = raw
        else:
            raw_accounts = []

        for acc in raw_accounts:
            accounts.append(self._normalize_account(acc))

        return {
            "accounts": accounts,
            "_normalized_by": "sentinel",
            "_source_bank": bank_id,
        }

    def _normalize_account(self, acc: dict) -> dict:
        """Tək hesabı normalize et."""
        return {
            "resourceId": acc.get("resourceId") or acc.get("id") or acc.get("accountId", ""),
            "iban": acc.get("iban") or acc.get("IBAN", ""),
            "currency": acc.get("currency") or acc.get("ccy") or acc.get("CCY", "GEL"),
            "name": acc.get("name") or acc.get("accountName") or acc.get("owner", ""),
            "product": acc.get("product") or acc.get("productType") or acc.get("type", ""),
            "status": acc.get("status") or "unknown",
            "links": self._normalize_links(acc),
        }

    def _normalize_links(self, obj: dict) -> dict:
        """_links vs links vs href struktur fərqini aradan qaldır."""
        links = obj.get("_links") or obj.get("links") or {}
        result = {}
        for key, val in links.items():
            if isinstance(val, dict):
                result[key] = val.get("href") or val.get("url") or str(val)
            elif isinstance(val, str):
                result[key] = val
        return result

    def normalize_balance_list(self, raw: Any, bank_id: str) -> dict:
        """Balans siyahısını normalize et."""
        balances = []

        if isinstance(raw, dict):
            if "balances" in raw:
                raw_balances = raw["balances"]
            elif "balance_list" in raw:
                raw_balances = raw["balance_list"]
            else:
                raw_balances = []
        elif isinstance(raw, list):
            raw_balances = raw
        else:
            raw_balances = []

        for bal in raw_balances:
            balances.append(self._normalize_balance(bal))

        return {"balances": balances, "_source_bank": bank_id}

    def _normalize_balance(self, bal: dict) -> dict:
        return {
            "balanceType": bal.get("balanceType") or bal.get("type") or "closingBooked",
            "balanceAmount": self._normalize_amount(
                bal.get("balanceAmount") or bal.get("amount") or bal
            ),
            "referenceDate": self._normalize_date(
                bal.get("referenceDate") or bal.get("date") or bal.get("asOf")
            ),
        }

    def normalize_transaction_list(self, raw: Any, bank_id: str) -> dict:
        """Tranzaksiya siyahısını normalize et."""
        transactions = {"booked": [], "pending": []}

        if isinstance(raw, dict):
            txns_obj = raw.get("transactions") or raw.get("transactionList") or []
            if isinstance(txns_obj, dict):
                booked = txns_obj.get("booked", [])
                pending = txns_obj.get("pending", [])
            elif isinstance(txns_obj, list):
                booked = txns_obj
                pending = []
            else:
                booked = []
                pending = []
        elif isinstance(raw, list):
            booked = raw
            pending = []
        else:
            booked = []
            pending = []

        transactions["booked"] = [self._normalize_transaction(t) for t in booked]
        transactions["pending"] = [self._normalize_transaction(t) for t in pending]
        return {"transactions": transactions, "_source_bank": bank_id}

    def _normalize_transaction(self, txn: dict) -> dict:
        return {
            "transactionId": txn.get("transactionId") or txn.get("id") or txn.get("txnId", ""),
            "transactionAmount": self._normalize_amount(
                txn.get("transactionAmount") or txn.get("amount")
            ),
            "bookingDate": self._normalize_date(
                txn.get("bookingDate") or txn.get("booking_date")
            ),
            "valueDate": self._normalize_date(
                txn.get("valueDate") or txn.get("value_date")
            ),
            "creditDebitIndicator": self._normalize_indicator(
                txn.get("creditDebitIndicator") or txn.get("direction") or txn.get("type")
            ),
            "status": txn.get("status") or txn.get("txnStatus") or "Booked",
            "remittanceInformationUnstructured": (
                txn.get("remittanceInformationUnstructured")
                or txn.get("description")
                or txn.get("reference")
                or ""
            ),
            "creditorName": txn.get("creditorName") or txn.get("merchant") or "",
        }

    def _normalize_amount(self, amount: Any) -> dict:
        """Fərqli amount quruluşlarını normalize et."""
        if isinstance(amount, dict):
            val = amount.get("amount") or amount.get("value") or amount.get("sum") or 0
            cur = amount.get("currency") or amount.get("ccy") or amount.get("CCY") or "GEL"
            return {"amount": f"{float(val):.2f}", "currency": str(cur).upper()}
        elif isinstance(amount, (int, float)):
            return {"amount": f"{float(amount):.2f}", "currency": "GEL"}
        return {"amount": "0.00", "currency": "GEL"}

    def _normalize_date(self, date_val: Any) -> Optional[str]:
        """Fərqli tarix formatlarını ISO 8601-ə çevir."""
        if not date_val:
            return None

        # Unix timestamp
        if isinstance(date_val, (int, float)) and date_val > 1_000_000_000:
            from datetime import datetime, timezone
            return datetime.fromtimestamp(date_val, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        if not isinstance(date_val, str):
            return str(date_val)

        # Slash format: YYYY/MM/DD HH:MM:SS
        slash = re.match(r"(\d{4})/(\d{2})/(\d{2})(?:\s(\d{2}):(\d{2}):(\d{2}))?", date_val)
        if slash:
            g = slash.groups()
            if g[3]:
                return f"{g[0]}-{g[1]}-{g[2]}T{g[3]}:{g[4]}:{g[5]}.000Z"
            return f"{g[0]}-{g[1]}-{g[2]}"

        # Artıq ISO format
        if re.match(r"\d{4}-\d{2}-\d{2}", date_val):
            return date_val

        return date_val

    def _normalize_indicator(self, val: str) -> str:
        """creditDebitIndicator normalize et."""
        if not val:
            return "DBIT"
        val = str(val).upper()
        if val in ("CRDT", "CREDIT", "CR", "IN", "DEPOSIT"):
            return "CRDT"
        return "DBIT"

    def normalize_payment_response(self, raw: Any, bank_id: str) -> dict:
        """Ödəniş cavabını normalize et."""
        if not isinstance(raw, dict):
            return {"error": "Invalid response format"}

        payment_id = raw.get("paymentId") or raw.get("id") or raw.get("payment_id", "")
        status = raw.get("transactionStatus") or self._map_payment_status(
            raw.get("status") or raw.get("state") or "RCVD"
        )
        links = self._normalize_links(raw)

        # Non-standard SCA URL-ləri standarta çevir
        if "scaRedirect" not in links:
            sca_url = raw.get("sca_url") or raw.get("auth_url") or raw.get("redirect")
            if sca_url:
                links["scaRedirect"] = sca_url

        return {
            "paymentId": payment_id,
            "transactionStatus": status,
            "_links": links,
            "_source_bank": bank_id,
        }

    def _map_payment_status(self, raw_status: str) -> str:
        mapping = {
            "received": "RCVD",
            "pending": "PDNG",
            "processing": "ACTC",
            "completed": "ACSC",
            "rejected": "RJCT",
            "cancelled": "CANC",
        }
        return mapping.get(str(raw_status).lower(), "RCVD")


# Singleton
normalizer = NormalizationLayer()
