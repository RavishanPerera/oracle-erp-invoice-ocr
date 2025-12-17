from typing import Optional, Dict, Any

from src.db import get_connection


def get_or_create_supplier(fields: Dict[str, Any]) -> Optional[int]:
    """
    Look up a supplier by name (and optionally email); create if missing.
    Returns supplier_id or None if no supplier_name was provided.
    """
    name = (fields.get("supplier_name") or "").strip()
    email = (fields.get("supplier_email") or "").strip() or None
    address = fields.get("supplier_address")
    phone = fields.get("supplier_phone")

    if not name:
        return None

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Try to find an existing supplier by name (and email when present)
        if email:
            cursor.execute(
                """
                SELECT supplier_id
                FROM suppliers
                WHERE name = :name AND email = :email
                FETCH FIRST 1 ROWS ONLY
                """,
                {"name": name, "email": email},
            )
        else:
            cursor.execute(
                """
                SELECT supplier_id
                FROM suppliers
                WHERE name = :name
                FETCH FIRST 1 ROWS ONLY
                """,
                {"name": name},
            )

        row = cursor.fetchone()
        if row:
            return int(row[0])

        # Insert new supplier
        cursor.execute(
            """
            INSERT INTO suppliers (name, address, email, phone)
            VALUES (:name, :address, :email, :phone)
            """,
            {
                "name": name,
                "address": address,
                "email": email,
                "phone": phone,
            },
        )
        conn.commit()

        cursor.execute(
            "SELECT supplier_id FROM suppliers WHERE name = :name ORDER BY supplier_id DESC FETCH FIRST 1 ROWS ONLY",
            {"name": name},
        )
        row = cursor.fetchone()
        return int(row[0]) if row else None

    finally:
        cursor.close()
        conn.close()


