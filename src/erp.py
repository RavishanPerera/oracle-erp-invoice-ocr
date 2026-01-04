import argparse
from pathlib import Path
from typing import Optional

from src.ocr_engine import extract_text_from_image, extract_text_from_pdf
from src.invoice_parser import parse_invoice_text
from src.text_parser import extract_line_items
from src.invoice_repository import insert_invoice
from src.invoice_items_repository import insert_line_items
from src.supplier_repository import get_or_create_supplier
from src.customer_repository import get_or_create_customer


DEFAULT_INVOICE_DIR = "data/invoices"
DEFAULT_OUTPUT_DIR = "data/output"


def process_file(input_path: Path, output_dir: Path) -> Optional[str]:
    """
    Run OCR on a single file and write both raw text and a simple
    structured JSON sidecar (if we can parse invoice fields).
    """
    print(f"\n📄 Processing: {input_path.name}")

    suffix = input_path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg"}:
        text = extract_text_from_image(str(input_path))
    elif suffix == ".pdf":
        text = extract_text_from_pdf(str(input_path))
    else:
        print(f"⚠️ Skipping unsupported file type: {input_path}")
        return None

    output_dir.mkdir(parents=True, exist_ok=True)

    # Save raw OCR text
    text_output_path = output_dir / f"{input_path.name}.txt"
    with text_output_path.open("w", encoding="utf-8") as f:
        f.write(text)
    print(f"📝 OCR text saved to: {text_output_path}")

    # -------------------------------
    # PARSE INVOICE HEADER FIELDS
    # -------------------------------
    fields = parse_invoice_text(text)

    # Fallback: if OCR/parser couldn't detect invoice number,
    # use filename stem (VERY IMPORTANT for multi-vendor invoices)
    if not fields.invoice_number:
        print("⚠️ Invoice number not detected from text, using filename")
        fields.invoice_number = input_path.stem

    # Clean common OCR artifacts
    if fields.invoice_number:
        fields.invoice_number = (
            fields.invoice_number.strip()
            .replace("—_", "")
            .replace("—", "")
            .replace("_", "")
        )

    fields_dict = fields.to_dict()

    print("🔎 PARSED INVOICE FIELDS:")
    for k, v in fields_dict.items():
        print(f"   {k}: {v}")

    json_output_path = output_dir / f"{input_path.name}.json"

    # -----------------------------------
    # ONLY PROCEED IF WE FOUND REAL DATA
    # -----------------------------------
    if not any(fields_dict.values()):
        print("❌ No invoice fields detected. Skipping DB insert.")
        return None

    # Save structured JSON
    import json
    with json_output_path.open("w", encoding="utf-8") as f:
        json.dump(fields_dict, f, indent=2, ensure_ascii=False)
    print(f"📦 Parsed invoice fields saved to: {json_output_path}")

    # -----------------------------------
    # RESOLVE SUPPLIER & CUSTOMER
    # -----------------------------------
    supplier_id = get_or_create_supplier(fields_dict)
    customer_id = get_or_create_customer(fields_dict)

    fields_dict["supplier_id"] = supplier_id
    fields_dict["customer_id"] = customer_id

    # -----------------------------------
    # INSERT INVOICE HEADER
    # -----------------------------------
    try:
        insert_invoice(fields_dict)
        print("✅ Invoice header inserted into database")
    except Exception as e:
        print(f"❌ Failed to insert invoice header: {e}")
        return None

    # -----------------------------------
    # EXTRACT & INSERT LINE ITEMS
    # -----------------------------------
    if fields.invoice_number:
        items = extract_line_items(text)
        if items:
            insert_line_items(fields.invoice_number, items)
            print(f"🧾 Inserted {len(items)} line items")
        else:
            print("ℹ️ No line items detected")

    return fields.invoice_number


def process_directory(input_dir: Path, output_dir: Path) -> None:
    """
    Process all supported invoice files in a directory.
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    for entry in sorted(input_dir.iterdir()):
        if not entry.is_file():
            continue
        process_file(entry, output_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch OCR for invoice PDFs and images."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=DEFAULT_INVOICE_DIR,
        help=f"Input file or directory (default: {DEFAULT_INVOICE_DIR})",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory where OCR output will be written (default: {DEFAULT_OUTPUT_DIR})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)

    if input_path.is_file():
        process_file(input_path, output_dir)
    else:
        process_directory(input_path, output_dir)


if __name__ == "__main__":
    main()
