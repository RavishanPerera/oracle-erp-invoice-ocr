from text_parser import parse_text_fields


def parse_invoice(ocr_text: str) -> dict:
    data = parse_text_fields(ocr_text)

    if not data["invoice_no"]:
        raise ValueError("Invoice number not detected")

    if not data["total_amount"]:
        raise ValueError("Total amount not detected")

    return {
        "invoice_no": data["invoice_no"],
        "invoice_date": data["invoice_date"] or "UNKNOWN",
        "total_amount": data["total_amount"],
        "supplier_name": data["supplier_name"] or "UNKNOWN",
        "customer_name": data["customer_name"] or "UNKNOWN"
    }
