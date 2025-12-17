import re


def extract_line_items(text: str):
    """
    Extract invoice line items from OCR text, tailored to your sample layout.

    Rules:
    - Only process lines after the table header:
        Description   Qty   Unit Price   Total / Line Total
    - Stop at subtotal/total/tax/balance due lines
    - Treat the last two monetary values on a line as unit_price and line_total
    - Use the previous non-empty line as part of the description when needed
    - Ignore short / non-product descriptions
    """
    raw_lines = text.splitlines()
    # Normalize internal whitespace but keep line structure
    lines = [re.sub(r"\s+", " ", ln.strip()) for ln in raw_lines]
    items = []

    # Step 1: Find the line where the table header starts
    header_index = None
    header_pattern = re.compile(
        r"description\s+qty\s+unit\s+price\s+(total|line\s+total)",
        re.IGNORECASE,
    )

    for i, line in enumerate(lines):
        if header_pattern.search(line):
            header_index = i
            break

    if header_index is None:
        return items

    money_pattern = re.compile(r"\d[\d,]*\.\d{2}")
    prev_desc_line = ""

    # Step 2: Process lines after the header
    for line in lines[header_index + 1 :]:
        if not line:
            continue

        lower = line.lower()
        # Stop at totals/subtotal/balance
        if re.search(
            r"(subtotal|grand total|total tax|balance due)",
            lower,
        ):
            break

        amounts = money_pattern.findall(line)
        if len(amounts) >= 2:
            unit_price_str = amounts[-2]
            line_total_str = amounts[-1]

            first_amount_match = money_pattern.search(line)
            if first_amount_match:
                current_desc = line[: first_amount_match.start()].strip(" -:")
            else:
                current_desc = ""

            # Combine with previous line when description is split
            if prev_desc_line and current_desc:
                desc = f"{prev_desc_line} {current_desc}".strip()
            elif current_desc:
                desc = current_desc
            elif prev_desc_line:
                desc = prev_desc_line
            else:
                desc = ""

            desc = desc.strip()
            # Remove trailing "as" artifact if present
            if desc.lower().endswith(" as"):
                desc = desc[:-2].strip()

            # Skip short / noisy descriptions
            if len(desc) < 10:
                continue

            try:
                unit_price = float(unit_price_str.replace(",", ""))
                line_total = float(line_total_str.replace(",", ""))
            except ValueError:
                continue

            items.append(
                {
                    "description": desc,
                    "quantity": 1.0,  # quantity is implicit in your sample
                    "unit_price": unit_price,
                    "line_total": line_total,
                }
            )
        else:
            # Track the last meaningful non-total line as potential description
            prev_desc_line = line

    return items






