from typing import List, Dict, Any

from src.db import get_connection


def _to_number(value):
    """
    Convert OCR/parsed numeric strings like '135,000.00' to a Python float.
    Returns None if the value is empty or cannot be parsed.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value

    text = str(value).strip()
    if not text:
        return None

    # Remove thousand separators and percent symbols
    text = text.replace(",", "").replace("%", "")

    try:
        return float(text)
    except ValueError:
        return None


def insert_invoice(invoice):
    """
    Insert a single invoice header row into the invoices table.

    Expects a dict compatible with InvoiceFields.to_dict(), e.g.
    {
        "invoice_number": "...",
        "invoice_date": "25/09/2025",
        "subtotal": "135,000.00",
        "total_tax": "0.00",
        "balance_due": "135,000.00",
        "total_amount": "135,000.00",
        "currency": "Rs."
    }
    """
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    INSERT INTO invoices (
        invoice_number,
        invoice_d,
        status,
        subtotal,
        discount,
        tax_rate,
        total_tax,
        balance_due,
        total_amount,
        currency,
        supplier_id,
        customer_id,
        payment_terms,
        bank_name,
        branch,
        account_number,
        payment_instructions
    )
    VALUES (
        :invoice_number,
        TO_DATE(:invoice_date, 'DD/MM/YYYY'),
        :status,
        :subtotal,
        :discount,
        :tax_rate,
        :total_tax,
        :balance_due,
        :total_amount,
        :currency,
        :supplier_id,
        :customer_id,
        :payment_terms,
        :bank_name,
        :branch,
        :account_number,
        :payment_instructions
    )
    """

    try:
        # Prepare a copy with only the columns actually used in the SQL,
        # and with numeric fields converted to real numbers.
        numeric_keys = (
            "subtotal",
            "discount",
            "tax_rate",
            "total_tax",
            "balance_due",
            "total_amount",
        )
        data = dict(invoice)
        for key in numeric_keys:
            data[key] = _to_number(data.get(key))

        params = {
            "invoice_number": data.get("invoice_number"),
            "invoice_date": data.get("invoice_date"),
            "status": data.get("invoice_status"),
            "subtotal": data.get("subtotal"),
            "discount": data.get("discount"),
            "tax_rate": data.get("tax_rate"),
            "total_tax": data.get("total_tax"),
            "balance_due": data.get("balance_due"),
            "total_amount": data.get("total_amount"),
            "currency": data.get("currency"),
            "supplier_id": data.get("supplier_id"),
            "customer_id": data.get("customer_id"),
            "payment_terms": data.get("payment_terms"),
            "bank_name": data.get("bank_name"),
            "branch": data.get("branch"),
            "account_number": data.get("account_number"),
            "payment_instructions": data.get("payment_instructions"),
        }

        cursor.execute(sql, params)
        conn.commit()
        print("Invoice inserted:", data.get("invoice_number"))

    except Exception as e:
        conn.rollback()
        print("Insert failed:", e)

    finally:
        cursor.close()
        conn.close()


def get_recent_invoices(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Fetch the most recent invoices for dashboard display, including
    supplier and customer names where available.
    """
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT
            i.invoice_number,
            i.invoice_d,
            i.status,
            i.subtotal,
            i.discount,
            i.tax_rate,
            i.total_tax,
            i.balance_due,
            i.total_amount,
            i.currency,
            i.created_at,
            s.name AS supplier_name,
            c.name AS customer_name
        FROM invoices i
        LEFT JOIN suppliers s ON i.supplier_id = s.supplier_id
        LEFT JOIN customers c ON i.customer_id = c.customer_id
        ORDER BY i.created_at DESC
        FETCH FIRST :limit ROWS ONLY
    """

    try:
        cursor.execute(sql, {"limit": limit})
        columns = [col[0].lower() for col in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        cursor.close()
        conn.close()


def get_invoice_by_number(invoice_number: str) -> Dict[str, Any] | None:
    """
    Fetch a single invoice with joined supplier & customer details
    for the detail view in the dashboard.
    """
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT
            i.invoice_number,
            i.invoice_d,
            i.status,
            i.subtotal,
            i.discount,
            i.tax_rate,
            i.total_tax,
            i.balance_due,
            i.total_amount,
            i.currency,
            i.payment_terms,
            i.bank_name,
            i.branch,
            i.account_number,
            i.payment_instructions,
            i.created_at,
            s.name AS supplier_name,
            s.address AS supplier_address,
            s.email AS supplier_email,
            s.phone AS supplier_phone,
            c.name AS customer_name,
            c.billing_address,
            c.shipping_address
        FROM invoices i
        LEFT JOIN suppliers s ON i.supplier_id = s.supplier_id
        LEFT JOIN customers c ON i.customer_id = c.customer_id
        WHERE i.invoice_number = :invoice_number
    """

    try:
        cursor.execute(sql, {"invoice_number": invoice_number})
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0].lower() for col in cursor.description]
        return dict(zip(columns, row))
    finally:
        cursor.close()
        conn.close()


def delete_invoice(invoice_number: str) -> None:
    """
    Delete a single invoice header row.
    Assumes related line items are deleted separately.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM invoices WHERE invoice_number = :invoice_number",
            {"invoice_number": invoice_number},
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

