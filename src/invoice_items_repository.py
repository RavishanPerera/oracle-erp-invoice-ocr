from typing import List, Dict, Any

from src.db import get_connection


def _to_number(value):
    """
    Convert numeric strings like '135,000.00' to a Python float.
    Returns None if the value is empty or cannot be parsed.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value

    text = str(value).strip()
    if not text:
        return None

    text = text.replace(",", "")

    try:
        return float(text)
    except ValueError:
        return None


def insert_line_items(invoice_number, items):
    """
    Insert multiple invoice line items for a given invoice_number.

    items is expected to be a list of dicts with keys:
      - description
      - quantity
      - unit_price
      - line_total
    """
    if not items:
        return

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    INSERT INTO invoice_items (
        invoice_number, description, quantity, unit_price, line_total
    ) VALUES (
        :invoice_number, :description, :quantity, :unit_price, :line_total
    )
    """

    try:
        for item in items:
            payload = {
                "invoice_number": invoice_number,
                "description": item.get("description"),
                "quantity": _to_number(item.get("quantity", 1)),
                "unit_price": _to_number(item.get("unit_price")),
                "line_total": _to_number(item.get("line_total")),
            }
            cursor.execute(sql, payload)

        conn.commit()
        print(f"{len(items)} line items inserted for invoice {invoice_number}")

    except Exception as e:
        conn.rollback()
        print("Insert failed:", e)

    finally:
        cursor.close()
        conn.close()


def get_items_for_invoice(invoice_number: str) -> List[Dict[str, Any]]:
    """
    Fetch all line items for a given invoice number.
    """
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT
            item_id,
            invoice_number,
            description,
            quantity,
            unit_price,
            line_total,
            created_at
        FROM invoice_items
        WHERE invoice_number = :invoice_number
        ORDER BY item_id
    """

    try:
        cursor.execute(sql, {"invoice_number": invoice_number})
        columns = [col[0].lower() for col in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        cursor.close()
        conn.close()


def delete_items_for_invoice(invoice_number: str) -> None:
    """
    Delete all line items for a given invoice number.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM invoice_items WHERE invoice_number = :invoice_number",
            {"invoice_number": invoice_number},
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()




