from text_parser import extract_line_items


def main() -> None:
    # Load OCR text produced by the pipeline
    with open("data/output/print.pdf.txt", "r", encoding="utf-8") as f:
        raw_text = f.read()

    items = extract_line_items(raw_text)

    for i, item in enumerate(items, 1):
        print(f"Item {i}:")
        print(f"  Description: {item['description']}")
        print(f"  Quantity: {item['quantity']}")
        print(f"  Unit Price: {item['unit_price']}")
        print(f"  Line Total: {item['line_total']}\n")


if __name__ == "__main__":
    main()


