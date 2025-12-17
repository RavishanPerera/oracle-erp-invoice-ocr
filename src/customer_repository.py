from typing import Optional, Dict, Any

from src.db import get_connection


def get_or_create_customer(fields: Dict[str, Any]) -> Optional[int]:
    """
    Look up a customer by name + billing address; create if missing.
    Returns customer_id or None if no customer_name was provided.
    """
    name = (fields.get("customer_name") or "").strip()
    billing_address = (fields.get("billing_address") or "").strip() or None
    shipping_address = fields.get("shipping_address") or billing_address

    if not name:
        return None

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Try to find an existing customer by name + billing address
        cursor.execute(
            """
            SELECT customer_id
            FROM customers
            WHERE name = :name
              AND (billing_address = :billing_address OR (:billing_address IS NULL AND billing_address IS NULL))
            FETCH FIRST 1 ROWS ONLY
            """,
            {"name": name, "billing_address": billing_address},
        )

        row = cursor.fetchone()
        if row:
            return int(row[0])

        # Insert new customer
        cursor.execute(
            """
            INSERT INTO customers (name, billing_address, shipping_address)
            VALUES (:name, :billing_address, :shipping_address)
            """,
            {
                "name": name,
                "billing_address": billing_address,
                "shipping_address": shipping_address,
            },
        )
        conn.commit()

        cursor.execute(
            """
            SELECT customer_id
            FROM customers
            WHERE name = :name
            ORDER BY customer_id DESC
            FETCH FIRST 1 ROWS ONLY
            """,
            {"name": name},
        )
        row = cursor.fetchone()
        return int(row[0]) if row else None

    finally:
        cursor.close()
        conn.close()


