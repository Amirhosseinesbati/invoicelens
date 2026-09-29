from decimal import Decimal

from invoicelens.rules import (
    amount,
    money_string,
    parse_date,
    quantize,
    validate_arithmetic,
)
from invoicelens.service import _safe_cell


def test_currency_rounding_and_locale_policy():
    assert amount("1,234.56") == Decimal("1234.56")
    assert amount("1.234,56") == Decimal("1234.56")
    assert amount("1,234", decimal_separator=",") == Decimal("1.234")
    assert quantize(Decimal("1.235"), "USD") == Decimal("1.24")
    assert quantize(Decimal("1.2345"), "KWD") == Decimal("1.235")
    assert money_string("1.371", "JPY") == "1371"
    assert parse_date("06/07/2026", "MDY") == "2026-06-07"
    assert parse_date("06/07/2026", "DMY") == "2026-07-06"
    assert parse_date("06/07/2026", "NONE") is None


def test_arithmetic_and_formula_escape():
    data = {
        "kind": "invoice",
        "fields": {
            key: {"value": value}
            for key, value in {
                "vendor": "Example",
                "number": "INV-1",
                "date": "2026-09-01",
                "currency": "USD",
                "subtotal": "100.00",
                "tax": "10.00",
                "freight": "0.00",
                "discounts": "0.00",
                "total": "111.00",
            }.items()
        },
        "lines": [
            {"sku": "A", "quantity": "2", "unit_price": "50.00", "amount": "100.00"}
        ],
    }
    findings = validate_arithmetic(data)
    assert [f["code"] for f in findings] == ["TOTAL_MISMATCH"]
    assert _safe_cell('=HYPERLINK("evil")').startswith("'")
    assert _safe_cell("-10.00") == "-10.00"
    assert _safe_cell("-cmd") == "'-cmd"


def test_unreadable_printed_tax_requires_review_before_total_mismatch():
    data = {
        "kind": "invoice",
        "fields": {
            "vendor": {"value": "Example"},
            "number": {"value": "INV-1"},
            "date": {"value": "2026-09-01"},
            "currency": {"value": "JPY"},
            "subtotal": {"value": "1267"},
            "tax": {"raw": "2a1", "value": None},
            "freight": {"value": "0"},
            "discounts": {"value": "0"},
            "total": {"value": "1508"},
        },
        "lines": [],
    }

    findings = validate_arithmetic(data)
    assert [item["code"] for item in findings] == ["ARITHMETIC_UNVERIFIED"]
    assert findings[0]["severity"] == "warning"
    assert findings[0]["details"]["unreadable_components"] == ["tax"]

    # An absent optional field is zero; a genuine mismatch remains an error.
    data["fields"]["tax"] = {"raw": None, "value": None}
    assert [item["code"] for item in validate_arithmetic(data)] == ["TOTAL_MISMATCH"]


def test_signed_credit_note_arithmetic_and_real_mismatch():
    data = {
        "kind": "credit_note",
        "fields": {
            "vendor": {"value": "Example"},
            "number": {"value": "CN-1"},
            "date": {"value": "2026-09-01"},
            "currency": {"value": "USD"},
            "subtotal": {"value": "-35.77"},
            "tax": {"value": "-0.00"},
            "freight": {"value": "0.00"},
            "discounts": {"value": "0.00"},
            "total": {"value": "-35.77"},
        },
        "lines": [
            {"sku": "A", "quantity": "-1", "unit_price": "35.77", "amount": "-35.77"}
        ],
    }

    assert validate_arithmetic(data) == []
    data["fields"]["total"]["value"] = "-30.77"
    assert [item["code"] for item in validate_arithmetic(data)] == ["TOTAL_MISMATCH"]
