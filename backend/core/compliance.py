"""
Sentinel — Compliance Checker (B3)
Berlin Group NextGenPSD2 standartına uyğunluq yoxlaması.
"""

import re
from datetime import datetime
from typing import Any

# ISO 8601 regex
ISO8601_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)

BERLIN_GROUP_STATUS_CODES = {
    "accounts": [200, 401, 403, 404, 429],
    "balances": [200, 401, 403, 404, 429],
    "transactions": [200, 401, 403, 404, 429],
    "payments": [201, 400, 401, 403, 404, 405, 429],
    "consent": [201, 400, 401, 403, 404, 429],
}

REQUIRED_FIELDS = {
    "accounts": ["accounts"],
    "account": ["resourceId", "iban", "currency", "name"],
    "balances": ["balances"],
    "balance": ["balanceType", "balanceAmount"],
    "amount": ["amount", "currency"],
    "transactions": ["transactions"],
    "transaction": ["transactionId", "transactionAmount", "bookingDate", "valueDate", "creditDebitIndicator"],
    "payment_response": ["paymentId", "transactionStatus", "_links"],
    "consent_response": ["consentId", "consentStatus", "_links"],
}

PAYMENT_STATUSES = {"RCVD", "PDNG", "ACTC", "ACWC", "ACSC", "ACCP", "ACSP", "RJCT", "CANC"}
CONSENT_STATUSES = {"received", "valid", "rejected", "expired", "terminatedByTpp"}
CREDIT_DEBIT = {"CRDT", "DBIT"}


class ComplianceIssue:
    def __init__(self, severity: str, code: str, message: str, field: str = None):
        self.severity = severity  # error | warning | info
        self.code = code
        self.message = message
        self.field = field

    def to_dict(self):
        d = {"severity": self.severity, "code": self.code, "message": self.message}
        if self.field:
            d["field"] = self.field
        return d


class ComplianceChecker:
    """
    Berlin Group NextGenPSD2 standartına uyğunluq yoxlayıcısı.
    """

    def check_response(
        self,
        endpoint_category: str,
        status_code: int,
        response_body: Any,
        response_headers: dict,
    ) -> dict:
        issues: list[ComplianceIssue] = []

        # 1. Status kodu yoxla
        allowed = BERLIN_GROUP_STATUS_CODES.get(endpoint_category, [200])
        if status_code not in allowed:
            issues.append(ComplianceIssue(
                "error", "INVALID_STATUS_CODE",
                f"Status {status_code} bu endpoint üçün Berlin Group standartında yoxdur. Gözlənilən: {allowed}",
            ))

        # 2. Uğur cavabı üçün ətraflı yoxlama
        if status_code in (200, 201) and isinstance(response_body, dict):
            category_issues = self._check_category(endpoint_category, response_body)
            issues.extend(category_issues)

        # 3. Xəta cavabı üçün quruluş yoxlaması
        if status_code >= 400 and isinstance(response_body, dict):
            if "tppMessages" not in response_body:
                issues.append(ComplianceIssue(
                    "warning", "MISSING_TPP_MESSAGES",
                    "Xəta cavabında 'tppMessages' sahəsi yoxdur (Berlin Group §8.6)",
                ))

        # 4. Header yoxlaması
        header_issues = self._check_headers(response_headers)
        issues.extend(header_issues)

        is_compliant = not any(i.severity == "error" for i in issues)
        score = self._calculate_compliance_score(issues)

        return {
            "is_compliant": is_compliant,
            "score": score,
            "issue_count": len(issues),
            "issues": [i.to_dict() for i in issues],
        }

    def _check_category(self, category: str, body: dict) -> list:
        issues = []
        if category == "accounts":
            issues.extend(self._check_required(body, REQUIRED_FIELDS["accounts"], "accounts response"))
            if "accounts" in body:
                for i, acc in enumerate(body["accounts"]):
                    issues.extend(self._check_required(acc, REQUIRED_FIELDS["account"], f"accounts[{i}]"))
                    if "iban" in acc:
                        issues.extend(self._check_iban(acc["iban"]))

        elif category == "balances":
            issues.extend(self._check_required(body, REQUIRED_FIELDS["balances"], "balances response"))
            if "balances" in body:
                for i, bal in enumerate(body["balances"]):
                    issues.extend(self._check_required(bal, REQUIRED_FIELDS["balance"], f"balances[{i}]"))
                    if "balanceType" in bal:
                        valid_types = {"closingBooked", "expected", "openingBooked", "interimAvailable", "interimBooked", "forwardAvailable"}
                        if bal["balanceType"] not in valid_types:
                            issues.append(ComplianceIssue(
                                "error", "INVALID_BALANCE_TYPE",
                                f"Yanlış balanceType: '{bal['balanceType']}'",
                                f"balances[{i}].balanceType",
                            ))
                    if "balanceAmount" in bal:
                        issues.extend(self._check_amount(bal["balanceAmount"], f"balances[{i}].balanceAmount"))
                    if "referenceDate" in bal:
                        issues.extend(self._check_date(bal["referenceDate"], f"balances[{i}].referenceDate"))

        elif category == "transactions":
            if "transactions" not in body:
                issues.append(ComplianceIssue("error", "MISSING_TRANSACTIONS", "Cavabda 'transactions' sahəsi yoxdur"))
            else:
                txns_obj = body["transactions"]
                if isinstance(txns_obj, dict):
                    booked = txns_obj.get("booked", [])
                    for i, txn in enumerate(booked):
                        issues.extend(self._check_transaction(txn, f"transactions.booked[{i}]"))
                elif isinstance(txns_obj, list):
                    for i, txn in enumerate(txns_obj):
                        issues.extend(self._check_transaction(txn, f"transactions[{i}]"))

        elif category == "payments":
            issues.extend(self._check_required(body, REQUIRED_FIELDS["payment_response"], "payment response"))
            if "transactionStatus" in body:
                if body["transactionStatus"] not in PAYMENT_STATUSES:
                    issues.append(ComplianceIssue(
                        "error", "INVALID_PAYMENT_STATUS",
                        f"Yanlış transactionStatus: '{body['transactionStatus']}'. ISO 20022 ISO kodu istifadə edin.",
                        "transactionStatus",
                    ))

        elif category == "consent":
            issues.extend(self._check_required(body, REQUIRED_FIELDS["consent_response"], "consent response"))
            if "consentStatus" in body:
                if body["consentStatus"] not in CONSENT_STATUSES:
                    issues.append(ComplianceIssue(
                        "error", "INVALID_CONSENT_STATUS",
                        f"Yanlış consentStatus: '{body['consentStatus']}'",
                        "consentStatus",
                    ))

        return issues

    def _check_transaction(self, txn: dict, path: str) -> list:
        issues = []
        issues.extend(self._check_required(txn, REQUIRED_FIELDS["transaction"], path))
        if "transactionAmount" in txn:
            issues.extend(self._check_amount(txn["transactionAmount"], f"{path}.transactionAmount"))
        if "bookingDate" in txn:
            issues.extend(self._check_date(txn["bookingDate"], f"{path}.bookingDate"))
        if "valueDate" in txn:
            issues.extend(self._check_date(txn["valueDate"], f"{path}.valueDate"))
        if "creditDebitIndicator" in txn:
            if txn["creditDebitIndicator"] not in CREDIT_DEBIT:
                issues.append(ComplianceIssue(
                    "error", "INVALID_CREDIT_DEBIT",
                    f"creditDebitIndicator 'CRDT' və ya 'DBIT' olmalıdır, alındı: '{txn['creditDebitIndicator']}'",
                    f"{path}.creditDebitIndicator",
                ))
        return issues

    def _check_required(self, obj: dict, fields: list, path: str) -> list:
        issues = []
        for field in fields:
            if field not in obj:
                issues.append(ComplianceIssue(
                    "error", "MISSING_REQUIRED_FIELD",
                    f"Məcburi sahə tapılmadı: '{field}'",
                    f"{path}.{field}",
                ))
        return issues

    def _check_amount(self, amount: Any, path: str) -> list:
        issues = []
        if not isinstance(amount, dict):
            issues.append(ComplianceIssue("error", "INVALID_AMOUNT_TYPE", f"Amount dict olmalıdır, alındı: {type(amount).__name__}", path))
            return issues
        if "amount" not in amount:
            issues.append(ComplianceIssue("error", "MISSING_AMOUNT_FIELD", "Amount.amount sahəsi yoxdur", f"{path}.amount"))
        elif not isinstance(amount["amount"], str):
            issues.append(ComplianceIssue(
                "error", "AMOUNT_NOT_STRING",
                f"Amount string olmalıdır (məs. '15.00'), alındı: {type(amount['amount']).__name__}",
                f"{path}.amount",
            ))
        if "currency" not in amount:
            issues.append(ComplianceIssue("error", "MISSING_CURRENCY", "Amount.currency sahəsi yoxdur", f"{path}.currency"))
        elif not re.match(r"^[A-Z]{3}$", str(amount.get("currency", ""))):
            issues.append(ComplianceIssue(
                "error", "INVALID_CURRENCY_FORMAT",
                f"Currency ISO 4217 formatında olmalıdır (3 böyük hərf), alındı: '{amount['currency']}'",
                f"{path}.currency",
            ))
        return issues

    def _check_date(self, date_str: Any, path: str) -> list:
        issues = []
        if isinstance(date_str, (int, float)):
            issues.append(ComplianceIssue(
                "error", "DATE_NOT_ISO8601",
                f"Tarix ISO 8601 string olmalıdır, alındı Unix timestamp: {date_str}",
                path,
            ))
        elif isinstance(date_str, str):
            # Date-only format acceptable for bookingDate/valueDate
            date_only = re.match(r"^\d{4}-\d{2}-\d{2}$", date_str)
            datetime_iso = ISO8601_PATTERN.match(date_str)
            slash_format = re.match(r"^\d{4}/\d{2}/\d{2}", date_str)
            if slash_format:
                issues.append(ComplianceIssue(
                    "error", "DATE_WRONG_FORMAT",
                    f"Slash format (YYYY/MM/DD) ISO 8601 deyil: '{date_str}'",
                    path,
                ))
            elif not date_only and not datetime_iso:
                issues.append(ComplianceIssue(
                    "warning", "DATE_FORMAT_UNCLEAR",
                    f"Tarix formatı standart deyil: '{date_str}'",
                    path,
                ))
        return issues

    def _check_iban(self, iban: str) -> list:
        issues = []
        if not re.match(r"^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$", iban.replace(" ", "")):
            issues.append(ComplianceIssue(
                "warning", "INVALID_IBAN_FORMAT",
                f"IBAN formatı yanlış görünür: '{iban}'",
                "iban",
            ))
        return issues

    def _check_headers(self, headers: dict) -> list:
        issues = []
        lower_headers = {k.lower(): v for k, v in headers.items()}
        if "x-request-id" not in lower_headers:
            issues.append(ComplianceIssue(
                "warning", "MISSING_REQUEST_ID",
                "X-Request-ID header tövsiyə olunur (Berlin Group §8.3)",
            ))
        return issues

    def _calculate_compliance_score(self, issues: list) -> float:
        if not issues:
            return 100.0
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        penalty = (error_count * 15) + (warning_count * 5)
        return max(0.0, 100.0 - penalty)


# Singleton
checker = ComplianceChecker()
