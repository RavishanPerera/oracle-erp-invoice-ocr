import re
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List


@dataclass
class InvoiceFields:
    # Identification
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    invoice_status: Optional[str] = "UNPAID"

    # Totals
    subtotal: Optional[str] = None
    discount: Optional[str] = None
    tax_rate: Optional[str] = None
    total_tax: Optional[str] = None
    balance_due: Optional[str] = None
    total_amount: Optional[str] = None
    currency: Optional[str] = None

    # Supplier (vendor)
    supplier_name: Optional[str] = None
    supplier_address: Optional[str] = None
    supplier_email: Optional[str] = None
    supplier_phone: Optional[str] = None

    # Customer
    customer_name: Optional[str] = None
    billing_address: Optional[str] = None
    shipping_address: Optional[str] = None

    # Payment & bank
    payment_terms: Optional[str] = None
    bank_name: Optional[str] = None
    branch: Optional[str] = None
    account_number: Optional[str] = None
    payment_instructions: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _first_match(patterns, text: str) -> Optional[str]:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            # Prefer a named group "value" if present, else the first group
            if "value" in m.groupdict():
                return m.group("value").strip()
            return m.group(1).strip()
    return None


def parse_invoice_text(text: str) -> InvoiceFields:
    """
    Very simple heuristic-based parser that tries to find
    key invoice fields from OCR'd text.
    """
    # Normalize whitespace to make regexes easier
    normalized = re.sub(r"[ \t]+", " ", text)

    invoice_number = _first_match(
        [
            r"invoice\s*(no\.?|number)[:\s]+(?P<value>[A-Z0-9_\-\/]+)",
            r"inv\s*#[:\s]+(?P<value>[A-Z0-9_\-\/]+)",
            # Handle patterns like: INVOICENO. | SEP25-TRN-ORC-INVO1 and OCR noise
            r"invoiceno\.?\s*[|:\-]*\s*(?P<value>\S+)",
        ],
        normalized,
    )

    invoice_date = _first_match(
        [
            r"invoice\s*date[:\s]+(?P<value>\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
            r"date[:\s]+(?P<value>\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
        ],
        normalized,
    )

    subtotal = _first_match(
        [
            r"subtotal\s+(?P<value>\d[\d,]*\.?\d{0,2})",
        ],
        normalized,
    )

    discount = _first_match(
        [
            r"discount\s*[-:]?\s*(?P<value>\d[\d,]*\.?\d{0,2})",
        ],
        normalized,
    )

    tax_rate = _first_match(
        [
            r"tax\s*rate\s+(?P<value>\d+\.?\d*%)",
        ],
        normalized,
    )

    total_tax = _first_match(
        [
            r"total\s+tax\s+(?P<value>\d[\d,]*\.?\d{0,2})",
        ],
        normalized,
    )

    balance_due = _first_match(
        [
            r"balance\s+due\s+(?P<value>\d[\d,]*\.?\d{0,2})",
        ],
        normalized,
    )

    # Prefer balance due as the main total amount when present
    total_amount = balance_due or _first_match(
        [
            r"(grand\s*total|total\s*amount|amount\s*due)[:\s]+(?P<value>[A-Z]{0,3}\s?\d[\d,]*\.?\d{0,2})",
            r"\btotal\b[:\s]+(?P<value>[A-Z]{0,3}\s?\d[\d,]*\.?\d{0,2})",
        ],
        normalized,
    )

    currency = _first_match(
        [
            r"\b(USD|EUR|GBP|LKR|INR)\b",
            r"(?P<value>Rs\.)",
            r"(?P<value>\$)",
        ],
        normalized,
    )

    # Status – default to UNPAID if nothing explicit is found
    invoice_status = _first_match(
        [
            r"\b(unpaid|paid|overdue|cancelled)\b",
        ],
        normalized,
    ) or "UNPAID"

    # Supplier – simple heuristics; will work well for your NOVITECH example
    supplier_name = _first_match(
        [
            r"(?P<value>[A-Z][A-Z0-9 &]+PRIVATE LIMITED)",
            r"(?P<value>[A-Z][A-Za-z0-9 &]+\(PVT\)\s+LTD)",
        ],
        normalized,
    )

    # Customer – e.g. 'SRI LANKA TELECOM PLC'
    customer_name = _first_match(
        [
            r"(?P<value>[A-Z][A-Z ]+PLC)",
        ],
        normalized,
    )

    # Bank & payment info
    payment_terms = _first_match(
        [
            r"within\s+(?P<value>\d+\s+business\s+days)",
            r"(?P<value>\d+\s*days)",
        ],
        normalized,
    )

    bank_name = _first_match(
        [
            r"(?P<value>[A-Z][A-Za-z ]+ Bank)",
        ],
        normalized,
    )

    branch = _first_match(
        [
            r"\bbranch[:\s]+(?P<value>[A-Za-z ]+)",
            r"\b(?P<value>Attidiya)\b",
        ],
        normalized,
    )

    account_number = _first_match(
        [
            r"\b(?P<value>\d{8,})\b",
        ],
        normalized,
    )

    payment_instructions = _first_match(
        [
            r"(Payment to be transferred[^\n]*)",
        ],
        text,
    )

    return InvoiceFields(
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        invoice_status=invoice_status,
        subtotal=subtotal,
        discount=discount,
        tax_rate=tax_rate,
        total_tax=total_tax,
        balance_due=balance_due,
        total_amount=total_amount,
        currency=currency,
        supplier_name=supplier_name,
        customer_name=customer_name,
        payment_terms=payment_terms,
        bank_name=bank_name,
        branch=branch,
        account_number=account_number,
        payment_instructions=payment_instructions,
    )


def extract_line_items(text: str) -> List[Dict[str, Optional[str]]]:
    """
    Extract line items from OCR text using table-aware heuristics.

    - Find the header line containing "Description" and "Qty"
    - Only parse lines after the header
    - Stop when reaching subtotal / totals section
    - Expect pattern: description [qty] unit_price line_total
    """
    # Keep original lines for structure, but normalize internal whitespace
    raw_lines = text.splitlines()
    lines = [re.sub(r"\s+", " ", ln.strip()) for ln in raw_lines]

    # 1) Find header line
    header_index = None
    for i, line in enumerate(lines):
        lower = line.lower()
        if "description" in lower and "qty" in lower:
            header_index = i
            break

    if header_index is None:
        return []

    items: List[Dict[str, Optional[str]]] = []

    # 2) Define patterns
    pattern_with_qty = re.compile(
        r"(?P<description>.+?)\s+"
        r"(?P<qty>\d+(?:\.\d+)?)\s+"
        r"(?P<unit_price>\d[\d,]*\.\d{1,2})\s+"
        r"(?P<line_total>\d[\d,]*\.\d{1,2})"
    )

    pattern_no_qty = re.compile(
        r"(?P<description>.+?)\s+"
        r"(?P<unit_price>\d[\d,]*\.\d{1,2})\s+"
        r"(?P<line_total>\d[\d,]*\.\d{1,2})"
    )

    # 3) Parse lines after header until totals
    for line in lines[header_index + 1 :]:
        if not line:
            continue

        lower = line.lower()
        if (
            "subtotal" in lower
            or "grand total" in lower
            or "total tax" in lower
            or "balance due" in lower
        ):
            break

        m = pattern_with_qty.match(line)
        qty: Optional[str]
        if m:
            desc = m.group("description").strip(" -:")
            qty = m.group("qty")
            unit_price = m.group("unit_price")
            line_total = m.group("line_total")
        else:
            m = pattern_no_qty.match(line)
            if not m:
                continue
            desc = m.group("description").strip(" -:")
            qty = "1"  # default when not explicitly present
            unit_price = m.group("unit_price")
            line_total = m.group("line_total")

        if not desc:
            continue

        items.append(
            {
                "description": desc,
                "quantity": qty,
                "unit_price": unit_price,
                "line_total": line_total,
            }
        )

    return items

