from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class ParsedDimension:
    raw: str
    value_mm: float
    confidence: float
    interpretation: str


_NUMBER = r"[-+]?\d+(?:[\.,]\d+)?"
_EXPLICIT = re.compile(rf"^\s*({_NUMBER})\s*(mm|cm|m)\s*$", re.IGNORECASE)
_BARE = re.compile(rf"^\s*({_NUMBER})\s*$")
_SCALE = re.compile(r"(?:\bM(?:aßstab)?\b\s*)?1\s*[:/]\s*(\d{1,4})", re.IGNORECASE)
_IMPERIAL = re.compile(
    r"(?P<feet>\d{1,4})\s*'\s*-?\s*"
    r"(?P<inch>\d{1,2})?"
    r"(?:\s+(?P<num>\d{1,2})\s*/\s*(?P<den>\d{1,2}))?\s*\""
)


def _normalize_arch_text(text: str) -> tuple[str, bool]:
    """Normalize common CAD / OCR punctuation without changing numeric meaning."""
    cleaned = (
        text.strip()
        .replace("Ø", "")
        .replace("~", "")
        .replace("≈", "")
        .replace("′", "'")
        .replace("’", "'")
        .replace("‘", "'")
        .replace("″", '"')
        .replace("“", '"')
        .replace("”", '"')
        .replace("<", "")
        .replace(">", "")
        .replace("|", "")
    )
    corrected = False
    if "'" in cleaned and '"' in cleaned:
        fixed = re.sub(r"(?<=[\-\s'])(?:O|Q)(?=\s*\")", "0", cleaned, flags=re.IGNORECASE)
        fixed = re.sub(r"(?<=\d)(?:O|Q)(?=\s*\")", "0", fixed, flags=re.IGNORECASE)
        if fixed != cleaned:
            cleaned = fixed
            corrected = True
    return cleaned, corrected


def _parse_imperial(cleaned: str, raw: str, corrected: bool) -> ParsedDimension | None:
    match = _IMPERIAL.search(cleaned)
    if not match:
        return None
    feet = int(match.group("feet"))
    inches = int(match.group("inch") or 0)
    numerator = int(match.group("num") or 0)
    denominator = int(match.group("den") or 1)
    if denominator <= 0 or inches >= 12 or numerator >= denominator:
        return None
    total_inches = feet * 12.0 + inches + (numerator / denominator)
    mm = total_inches * 25.4
    if not (20.0 <= mm <= 1_000_000.0):
        return None
    confidence = 0.91 if corrected else 0.96
    return ParsedDimension(raw, mm, confidence, "imperial_feet_inches")


def parse_dimension(text: str) -> ParsedDimension | None:
    cleaned, corrected = _normalize_arch_text(text)
    imperial = _parse_imperial(cleaned, text, corrected)
    if imperial is not None:
        return imperial
    metric_cleaned = cleaned.replace("'", "").replace('"', "")
    match = _EXPLICIT.match(metric_cleaned)
    if match:
        value = float(match.group(1).replace(",", "."))
        unit = match.group(2).lower()
        factor = {"mm": 1.0, "cm": 10.0, "m": 1000.0}[unit]
        mm = value * factor
        if 20.0 <= mm <= 100000.0:
            return ParsedDimension(text, mm, 0.98, f"explicit_{unit}")
        return None
    match = _BARE.match(metric_cleaned)
    if not match:
        return None
    token = match.group(1)
    numeric = float(token.replace(",", "."))
    has_decimal = "," in token or "." in token
    if has_decimal and 0.1 <= numeric < 100.0:
        return ParsedDimension(text, numeric * 1000.0, 0.88, "bare_decimal_as_m")
    if not has_decimal and 300.0 <= numeric <= 100000.0:
        return ParsedDimension(text, numeric, 0.86, "bare_integer_as_mm")
    return None


def parse_scale_denominator(text: str) -> int | None:
    match = _SCALE.search(text)
    if not match:
        return None
    denominator = int(match.group(1))
    if 1 <= denominator <= 1000:
        return denominator
    return None
