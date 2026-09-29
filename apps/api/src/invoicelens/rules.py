import hashlib
import json
import re
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CURRENCY_SCALE = {"JPY": 0, "KRW": 0, "BHD": 3, "KWD": 3, "OMR": 3}
SUPPORTED_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "AUD", "JPY", "KRW", "BHD", "KWD", "OMR", "CHF"}
MONEY_FIELDS = {"subtotal", "tax", "freight", "discounts", "total"}
DATE_FIELDS = {"date", "due_date"}


def amount(value: str | None, decimal_separator: str = ".") -> Decimal | None:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace("−", "-")
    text = re.sub(r"^[^\d+\-,.]+|[^\d,.]+$", "", text)
    if not text or text in {"-", ".", ","}:
        return None
    if "," in text and "." in text:
        decimal_separator = "," if text.rfind(",") > text.rfind(".") else "."
        grouping_separator = "." if decimal_separator == "," else ","
        text = text.replace(grouping_separator, "").replace(decimal_separator, ".")
    elif "," in text:
        parts = text.split(",")
        text = (
            text.replace(",", ".")
            if decimal_separator == ","
            else "".join(parts)
            if len(parts[-1]) == 3 and len(parts) > 1
            else text.replace(",", ".")
        )
    elif "." in text and decimal_separator == ",":
        parts = text.split(".")
        if len(parts[-1]) == 3 and len(parts) > 1:
            text = "".join(parts)
    try:
        result = Decimal(text)
    except InvalidOperation:
        return None
    if not result.is_finite():
        return None
    return -result if negative else result


def quantize(value: Decimal, currency: str | None) -> Decimal:
    scale = CURRENCY_SCALE.get((currency or "").upper(), 2)
    return value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)


def money_string(
    value: str | None, currency: str | None, decimal_separator: str = "."
) -> str | None:
    source = str(value).strip() if value is not None else None
    if source and currency in {"JPY", "KRW"} and re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", source):
        source = source.replace(",", "").replace(".", "")
    parsed = amount(source, decimal_separator)
    return format(quantize(parsed, currency), "f") if parsed is not None else None


def parse_date(value: str | None, order: str = "MDY") -> str | None:
    if not value:
        return None
    text = value.strip()
    slash_formats = ("%m/%d/%Y", "%d/%m/%Y") if order == "MDY" else ("%d/%m/%Y", "%m/%d/%Y")
    if order == "NONE" and re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", text):
        first, second, _ = text.split("/")
        if int(first) <= 12 and int(second) <= 12:
            return None
    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        *slash_formats,
        "%d.%m.%Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def normalize_field(
    key: str,
    value: str | None,
    currency: str | None = None,
    date_order: str = "MDY",
    decimal_separator: str = ".",
) -> str | None:
    if value is None or not str(value).strip():
        return None
    if key in MONEY_FIELDS or key.endswith(".amount") or key.endswith(".unit_price"):
        return money_string(str(value), currency, decimal_separator)
    if key.endswith(".quantity"):
        parsed = amount(str(value), decimal_separator)
        return format(parsed.normalize(), "f") if parsed is not None else None
    if key in DATE_FIELDS:
        return parse_date(str(value), date_order)
    if key == "currency":
        candidate = str(value).upper().strip()
        symbols = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}
        return (
            symbols.get(candidate, candidate)
            if symbols.get(candidate, candidate) in SUPPORTED_CURRENCIES
            else None
        )
    return str(value).strip()


def content_hash(data: dict) -> str:
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def validate_arithmetic(data: dict) -> list[dict]:
    if data.get("kind") == "purchase_order":
        return []
    fields = data.get("fields", {})
    currency = fields.get("currency", {}).get("value")
    findings: list[dict] = []
    subtotal = amount(fields.get("subtotal", {}).get("value"))
    optional_fields = ("tax", "freight", "discounts")
    unreadable_components = [
        key
        for key in optional_fields
        if fields.get(key, {}).get("raw") and amount(fields.get(key, {}).get("value")) is None
    ]
    tax = amount(fields.get("tax", {}).get("value")) or Decimal(0)
    freight = amount(fields.get("freight", {}).get("value")) or Decimal(0)
    discounts = amount(fields.get("discounts", {}).get("value")) or Decimal(0)
    total = amount(fields.get("total", {}).get("value"))
    if currency is None:
        findings.append(
            {
                "code": "MISSING_CURRENCY",
                "severity": "warning",
                "message": "Currency is missing or unsupported",
                "details": {},
            }
        )
    if total is None:
        findings.append(
            {
                "code": "MISSING_TOTAL",
                "severity": "warning",
                "message": "Total is missing or unreadable",
                "details": {},
            }
        )
    if subtotal is not None and total is not None:
        expected = quantize(subtotal + tax + freight - discounts, currency)
        actual = quantize(total, currency)
        if expected != actual:
            if unreadable_components:
                findings.append(
                    {
                        "code": "ARITHMETIC_UNVERIFIED",
                        "severity": "warning",
                        "message": "Cannot verify total until the unreadable printed components are reviewed",
                        "details": {
                            "unreadable_components": unreadable_components,
                            "known_components_total": format(expected, "f"),
                            "actual": format(actual, "f"),
                        },
                    }
                )
            else:
                findings.append(
                    {
                        "code": "TOTAL_MISMATCH",
                        "severity": "error",
                        "message": f"Expected {expected} from subtotal + tax + freight - discounts; source total is {actual}",
                        "details": {
                            "expected": format(expected, "f"),
                            "actual": format(actual, "f"),
                            "formula": "subtotal + tax + freight - discounts",
                        },
                    }
                )
    for index, line in enumerate(data.get("lines", [])):
        quantity = amount(line.get("quantity"))
        unit_price = amount(line.get("unit_price"))
        line_amount = amount(line.get("amount"))
        if quantity is None or unit_price is None or line_amount is None:
            continue
        expected = quantize(quantity * unit_price, currency)
        actual = quantize(line_amount, currency)
        if expected != actual:
            findings.append(
                {
                    "code": "LINE_AMOUNT_MISMATCH",
                    "severity": "error",
                    "message": f"Line {index + 1}: {quantity} × {unit_price} = {expected}, source shows {actual}",
                    "details": {
                        "line_index": index,
                        "expected": format(expected, "f"),
                        "actual": format(actual, "f"),
                    },
                }
            )
    if data.get("kind") in {"invoice", "credit_note"}:
        for key, label in (("vendor", "Vendor"), ("number", "Invoice number"), ("date", "Date")):
            if not fields.get(key, {}).get("value"):
                findings.append(
                    {
                        "code": f"MISSING_{key.upper()}",
                        "severity": "warning",
                        "message": f"{label} is missing or unreadable",
                        "details": {"field": key},
                    }
                )
    return findings
