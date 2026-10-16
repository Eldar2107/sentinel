"""
Sentinel — Schema Drift Monitor (A4, A5)
JSON cavablarındakı struktur dəyişikliklərini aşkar edir.
"""

import hashlib
import json
from typing import Any


class DriftDetector:
    """
    İki JSON cavabı arasındakı struktur fərqlərini tapır.
    Breaking vs non-breaking növlərini fərqləndirir.
    """

    def extract_schema_fingerprint(self, obj: Any, path: str = "") -> dict:
        """Cavabın struktur izini (schema fingerprint) çıxarır."""
        if isinstance(obj, dict):
            return {
                "_type": "object",
                "_keys": sorted(obj.keys()),
                "_children": {
                    k: self.extract_schema_fingerprint(v, f"{path}.{k}")
                    for k, v in obj.items()
                }
            }
        elif isinstance(obj, list):
            if obj:
                return {
                    "_type": "array",
                    "_item_schema": self.extract_schema_fingerprint(obj[0], f"{path}[0]")
                }
            return {"_type": "array", "_item_schema": None}
        else:
            return {"_type": type(obj).__name__, "_value_sample": self._sample(obj)}

    def _sample(self, val: Any) -> str:
        """Dəyərin nümunəsini saxla (PII olmadan)."""
        if isinstance(val, str):
            # Tarix formatını aşkar et
            import re
            if re.match(r"\d{4}-\d{2}-\d{2}", val):
                return "ISO_DATE"
            elif re.match(r"\d{4}/\d{2}/\d{2}", val):
                return "SLASH_DATE"
            elif re.match(r"\d{4}-\d{2}-\d{2}T", val):
                return "ISO_DATETIME"
            elif re.match(r"[A-Z]{2}\d{2}", val):
                return "IBAN_LIKE"
            return f"str(len={len(val)})"
        elif isinstance(val, int) and val > 1000000000:
            return "UNIX_TIMESTAMP_LIKE"
        elif isinstance(val, float):
            return "float"
        elif isinstance(val, int):
            return "int"
        elif isinstance(val, bool):
            return "bool"
        return str(type(val).__name__)

    def fingerprint_hash(self, obj: Any) -> str:
        """Struktur izi üçün SHA-256 hash."""
        fp = self.extract_schema_fingerprint(obj)
        canonical = json.dumps(fp, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def compare(self, baseline: Any, current: Any, path: str = "") -> list[dict]:
        """
        Baseline ilə cari cavabı müqayisə et.
        Fərqlərin siyahısını qaytarır.
        """
        diffs = []
        b_fp = self.extract_schema_fingerprint(baseline, path)
        c_fp = self.extract_schema_fingerprint(current, path)
        self._diff_fingerprints(b_fp, c_fp, path, diffs)
        return diffs

    def _diff_fingerprints(self, base: dict, curr: dict, path: str, diffs: list):
        if base.get("_type") != curr.get("_type"):
            diffs.append({
                "field_path": path or "root",
                "drift_type": "type_changed",
                "expected": base.get("_type"),
                "actual": curr.get("_type"),
                "severity": "critical",
                "description": f"Tip dəyişdi: {base.get('_type')} → {curr.get('_type')}",
            })
            return

        if base["_type"] == "object":
            base_keys = set(base.get("_keys", []))
            curr_keys = set(curr.get("_keys", []))

            for missing_key in base_keys - curr_keys:
                diffs.append({
                    "field_path": f"{path}.{missing_key}" if path else missing_key,
                    "drift_type": "field_removed",
                    "expected": missing_key,
                    "actual": None,
                    "severity": "critical",
                    "description": f"Sahə silindi: '{missing_key}'",
                })

            for added_key in curr_keys - base_keys:
                diffs.append({
                    "field_path": f"{path}.{added_key}" if path else added_key,
                    "drift_type": "field_added",
                    "expected": None,
                    "actual": added_key,
                    "severity": "info",
                    "description": f"Yeni sahə əlavə edildi: '{added_key}'",
                })

            for common_key in base_keys & curr_keys:
                child_path = f"{path}.{common_key}" if path else common_key
                base_child = base.get("_children", {}).get(common_key, {})
                curr_child = curr.get("_children", {}).get(common_key, {})
                self._diff_fingerprints(base_child, curr_child, child_path, diffs)

        elif base["_type"] in ("str", "int", "float"):
            b_sample = base.get("_value_sample", "")
            c_sample = curr.get("_value_sample", "")
            if b_sample != c_sample:
                # Format dəyişikliyi aşkar et
                date_formats = {"ISO_DATE", "ISO_DATETIME", "SLASH_DATE", "UNIX_TIMESTAMP_LIKE"}
                if b_sample in date_formats and c_sample in date_formats:
                    diffs.append({
                        "field_path": path,
                        "drift_type": "format_changed",
                        "expected": b_sample,
                        "actual": c_sample,
                        "severity": "warning",
                        "description": f"Tarix formatı dəyişdi: {b_sample} → {c_sample}",
                    })
                elif b_sample != c_sample:
                    diffs.append({
                        "field_path": path,
                        "drift_type": "value_format_changed",
                        "expected": b_sample,
                        "actual": c_sample,
                        "severity": "info",
                        "description": f"Dəyər formatı dəyişdi: {b_sample} → {c_sample}",
                    })

        elif base["_type"] == "array":
            b_item = base.get("_item_schema")
            c_item = curr.get("_item_schema")
            if b_item and c_item:
                self._diff_fingerprints(b_item, c_item, f"{path}[]", diffs)

    def extract_field_profiles(self, responses: list[Any]) -> dict:
        """
        Çoxsaylı cavabdan sahə profilini çıxar (A5 - Format Profilyeri).
        Hansı bankın hansı tarix formatını istifadə etdiyini müəyyən edir.
        """
        import re
        profiles = {
            "date_formats": {},
            "amount_types": {},
            "structure_variants": set(),
        }

        date_patterns = {
            "ISO_DATETIME": re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),
            "ISO_DATE": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
            "SLASH_FORMAT": re.compile(r"\d{4}/\d{2}/\d{2}"),
            "UNIX_TIMESTAMP": re.compile(r"^\d{10}$"),
        }

        for resp in responses:
            self._scan_values(resp, date_patterns, profiles)

        profiles["structure_variants"] = list(profiles["structure_variants"])
        return profiles

    def _scan_values(self, obj: Any, patterns: dict, profiles: dict):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str):
                    for fmt_name, pattern in patterns.items():
                        if pattern.search(v):
                            profiles["date_formats"][fmt_name] = profiles["date_formats"].get(fmt_name, 0) + 1
                elif isinstance(v, int) and v > 1_000_000_000:
                    profiles["date_formats"]["UNIX_TIMESTAMP"] = profiles["date_formats"].get("UNIX_TIMESTAMP", 0) + 1
                elif isinstance(v, (dict, list)):
                    self._scan_values(v, patterns, profiles)
        elif isinstance(obj, list):
            for item in obj:
                self._scan_values(item, patterns, profiles)


# Singleton
drift_detector = DriftDetector()
