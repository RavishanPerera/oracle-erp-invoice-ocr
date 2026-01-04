import re
from typing import Optional


def normalize(text: str) -> str:
    return (
        text.lower()
        .replace(",", "")
        .replace("\n", " ")
        .replace("\t", " ")
    )


def find_first(patterns, text) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def extract_invoice_number(text: str) -> Optional[str]:
    patterns = [
        r"invoice\s*(?:no|number|#)\s*[:\-]?\s*([a-z0-9\-\/]+)",
        r"bill\s*(?:no|number|#)\s*[:\-]?\s*([a-z0-9\-\/]+)",
        r"document\s*no\s*[:\-]?\s*([a-z0-9\-\/]+)",
        r"#\s*(inv[-\s]?\d+)"
    ]
    return find_first(patterns, text)


def extract_invoice_date(text: str) -> Optional[str]:
    patterns = [
        r"invoice\s*date\s*[:\-]?\s*([0-9]{2}\s[a-z]{3}\s[0-9]{4})",
        r"date\s*[:\-]?\s*([0-9]{2}\s[a-z]{3}\s[0-9]{4})",
        r"([0-9]{4}-[0-9]{2}-[0-9]{2})",
        r"([0-9]{2}/[0-9]{2}/[0-9]{4})"
    ]
    return find_first(patterns, text)


def extract_total_amount(text: str) -> Optional[float]:
    patterns = [
        r"(?:grand\s*total|total\s*amount|amount\s*due|net\s*total)\s*[:\-]?\s*(?:lkr|rs|\$)?\s*([0-9]+\.[0-9]{2})",
        r"(?:lkr|rs|\$)\s*([0-9]+\.[0-9]{2})"
    ]
    value = find_first(patterns, text)
    return float(value) if value else None


def extract_party(text: str, labels) -> Optional[str]:
    for label in labels:
        pattern = rf"{label}\s*[:\-]?\s*([a-z0-9\s\.\,&]+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def parse_text_fields(raw_text: str) -> dict:
    text = normalize(raw_text)

    return {
        "invoice_no": extract_invoice_number(text),
        "invoice_date": extract_invoice_date(text),
        "total_amount": extract_total_amount(text),
        "supplier_name": extract_party(text, ["from", "supplier", "seller"]),
        "customer_name": extract_party(text, ["bill to", "billed to", "customer", "client"])
    }
