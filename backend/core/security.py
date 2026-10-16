"""
Sentinel — Security Scanner (B6, B7)
TLS, sertifikat, təhlükəsizlik başlıqları və SCA axınının yoxlanması.
"""

import ssl
import socket
import re
from datetime import datetime, timezone
from typing import Optional


class SecurityScanner:
    """
    API endpoint-lərinin təhlükəsizlik profilini analiz edir.
    Sandbox/simulyasiya mühitinə uyğunlaşdırılmıb.
    """

    SECURITY_HEADERS = [
        "strict-transport-security",
        "content-security-policy",
        "x-content-type-options",
        "x-frame-options",
        "x-xss-protection",
        "referrer-policy",
        "permissions-policy",
    ]

    def scan_headers(self, response_headers: dict) -> dict:
        """HTTP cavab başlıqlarını analiz et."""
        lower = {k.lower(): v for k, v in response_headers.items()}
        issues = []
        present = []

        # HSTS
        if "strict-transport-security" in lower:
            hsts = lower["strict-transport-security"]
            present.append("HSTS")
            if "max-age" in hsts:
                max_age = re.search(r"max-age=(\d+)", hsts)
                if max_age and int(max_age.group(1)) < 31536000:
                    issues.append({
                        "code": "WEAK_HSTS",
                        "message": "HSTS max-age 1 ildən (31536000 saniyə) az",
                        "severity": "warning",
                    })
            if "includeSubDomains" not in hsts:
                issues.append({
                    "code": "HSTS_NO_SUBDOMAINS",
                    "message": "HSTS 'includeSubDomains' direktivi yoxdur",
                    "severity": "info",
                })
        else:
            issues.append({
                "code": "MISSING_HSTS",
                "message": "Strict-Transport-Security başlığı yoxdur",
                "severity": "critical",
            })

        # CSP
        if "content-security-policy" in lower:
            present.append("CSP")
            csp = lower["content-security-policy"]
            if "unsafe-inline" in csp:
                issues.append({
                    "code": "CSP_UNSAFE_INLINE",
                    "message": "CSP 'unsafe-inline' direktivi XSS riskini artırır",
                    "severity": "warning",
                })
        else:
            issues.append({
                "code": "MISSING_CSP",
                "message": "Content-Security-Policy başlığı yoxdur",
                "severity": "warning",
            })

        # X-Content-Type-Options
        if "x-content-type-options" in lower:
            present.append("X-Content-Type-Options")
            if lower["x-content-type-options"].strip().lower() != "nosniff":
                issues.append({
                    "code": "INVALID_XCTO",
                    "message": "X-Content-Type-Options 'nosniff' olmalıdır",
                    "severity": "warning",
                })
        else:
            issues.append({
                "code": "MISSING_XCTO",
                "message": "X-Content-Type-Options başlığı yoxdur",
                "severity": "warning",
            })

        # X-Frame-Options
        if "x-frame-options" in lower:
            present.append("X-Frame-Options")
        else:
            issues.append({
                "code": "MISSING_XFO",
                "message": "X-Frame-Options başlığı yoxdur (clickjacking riski)",
                "severity": "info",
            })

        score = self._header_score(issues, len(self.SECURITY_HEADERS))
        return {
            "present_headers": present,
            "missing_count": len([i for i in issues if "MISSING" in i["code"]]),
            "issues": issues,
            "score": score,
        }

    def check_sca_flow(self, response_body: dict) -> dict:
        """
        SCA (Strong Customer Authentication) axınını yoxla.
        Berlin Group PSD2 §5.3: ödəniş/consent cavabında scaRedirect/scaOAuth link olmalıdır.
        """
        issues = []
        has_sca = False

        if not isinstance(response_body, dict):
            return {"has_sca": False, "issues": ["Cavab dict deyil"], "score": 0}

        links = response_body.get("_links") or response_body.get("links") or {}
        if isinstance(links, dict):
            sca_keys = {"scaRedirect", "scaOAuth", "updatePsuAuthentication", "authoriseTransaction"}
            if any(k in links for k in sca_keys):
                has_sca = True
            elif any("sca" in k.lower() for k in links.keys()):
                has_sca = True

        if not has_sca:
            # Non-standard SCA URL yoxla
            for key in ["sca_url", "auth_url", "redirect", "authorization"]:
                if key in response_body:
                    has_sca = True
                    issues.append({
                        "code": "NON_STANDARD_SCA_FIELD",
                        "message": f"SCA URL standart '_links.scaRedirect' əvəzinə '{key}' sahəsindədir",
                        "severity": "warning",
                    })
                    break

            if not has_sca:
                issues.append({
                    "code": "MISSING_SCA_REDIRECT",
                    "message": "Ödəniş/consent cavabında SCA redirect linki yoxdur (PSD2 RTS Art. 30)",
                    "severity": "critical",
                })

        score = 100.0 if (has_sca and not issues) else (60.0 if has_sca else 0.0)
        return {
            "has_sca": has_sca,
            "sca_compliant": has_sca and not any(i["severity"] == "critical" for i in issues),
            "issues": issues,
            "score": score,
        }

    def check_token_exposure(self, response_body: dict, response_headers: dict) -> dict:
        """
        Xəta mesajlarında məlumat sızması yoxla (B7).
        """
        issues = []
        sensitive_patterns = [
            (re.compile(r"password", re.I), "Password"),
            (re.compile(r"secret", re.I), "Secret"),
            (re.compile(r"token", re.I), "Token"),
            (re.compile(r"private.?key", re.I), "Private Key"),
            (re.compile(r"stack.?trace", re.I), "Stack Trace"),
            (re.compile(r"sql|database|db.error", re.I), "SQL/DB Error"),
            (re.compile(r"exception|traceback", re.I), "Exception Detail"),
        ]

        body_str = str(response_body)
        for pattern, label in sensitive_patterns:
            if pattern.search(body_str):
                issues.append({
                    "code": "INFO_LEAKAGE",
                    "message": f"Cavabda həssas məlumat aşkar edildi: {label}",
                    "severity": "critical",
                })

        score = 100.0 if not issues else max(0.0, 100.0 - len(issues) * 30)
        return {"leakage_detected": bool(issues), "issues": issues, "score": score}

    def simulate_tls_check(self, bank_id: str) -> dict:
        """
        Sandbox mühitindəki TLS konfiqurasiyasını simulyasiya et.
        Hər bankın profilinə uyğun nəticə.
        """
        profiles = {
            "bank_a": {
                "tls_version": "TLSv1.3",
                "cipher": "TLS_AES_256_GCM_SHA384",
                "cert_days_remaining": 287,
                "issues": [],
                "score": 100.0,
            },
            "bank_b": {
                "tls_version": "TLSv1.2",
                "cipher": "ECDHE-RSA-AES128-GCM-SHA256",
                "cert_days_remaining": 45,
                "issues": [
                    {"code": "OLD_TLS", "message": "TLS 1.2 istifadəsindədir, TLS 1.3 tövsiyə olunur", "severity": "warning"},
                    {"code": "CERT_EXPIRY_SOON", "message": "Sertifikat 45 gün ərzində bitəcək", "severity": "warning"},
                ],
                "score": 65.0,
            },
            "bank_c": {
                "tls_version": "TLSv1.2",
                "cipher": "AES128-SHA",
                "cert_days_remaining": 8,
                "issues": [
                    {"code": "OLD_TLS", "message": "TLS 1.2 istifadəsindədir", "severity": "warning"},
                    {"code": "WEAK_CIPHER", "message": "Zəif cipher suite istifadəsindədir: AES128-SHA", "severity": "critical"},
                    {"code": "CERT_CRITICAL", "message": "Sertifikat 8 gün ərzində bitəcək — kritik!", "severity": "critical"},
                ],
                "score": 20.0,
            },
        }
        return profiles.get(bank_id, {"tls_version": "unknown", "issues": [], "score": 50.0})

    def full_scan(self, bank_id: str, response_headers: dict, response_body: dict,
                  endpoint_type: str = None) -> dict:
        """Tam təhlükəsizlik skanı."""
        header_result = self.scan_headers(response_headers)
        tls_result = self.simulate_tls_check(bank_id)
        token_result = self.check_token_exposure(response_body, response_headers)

        sca_result = None
        if endpoint_type in ("payments", "consent"):
            sca_result = self.check_sca_flow(response_body)

        all_issues = (
            header_result["issues"]
            + tls_result["issues"]
            + token_result["issues"]
            + (sca_result["issues"] if sca_result else [])
        )

        critical = sum(1 for i in all_issues if i["severity"] == "critical")
        warnings = sum(1 for i in all_issues if i["severity"] == "warning")

        # Ağırlıqlı skor
        weights = {"headers": 0.30, "tls": 0.40, "token": 0.20, "sca": 0.10}
        score = (
            header_result["score"] * weights["headers"]
            + tls_result["score"] * weights["tls"]
            + token_result["score"] * weights["token"]
        )
        if sca_result:
            score = score * 0.9 + sca_result["score"] * weights["sca"]

        return {
            "overall_score": round(score, 1),
            "critical_count": critical,
            "warning_count": warnings,
            "tls": tls_result,
            "headers": header_result,
            "token_exposure": token_result,
            "sca": sca_result,
            "all_issues": all_issues,
        }

    def _header_score(self, issues: list, total_headers: int) -> float:
        critical = sum(1 for i in issues if i["severity"] == "critical")
        warnings = sum(1 for i in issues if i["severity"] == "warning")
        penalty = critical * 20 + warnings * 8
        return max(0.0, 100.0 - penalty)


# Singleton
scanner = SecurityScanner()
