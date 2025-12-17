## ERP Invoice OCR – Project Overview

This project is an end‑to‑end **invoice OCR and ingestion system**:

- Takes **PDF invoices** as input.
- Uses **Tesseract OCR + pdf2image** to extract text.
- Parses structured invoice data (header, supplier, customer, totals, line items).
- Persists everything into an **Oracle XE** database.
- Exposes a **modern Flask dashboard** to upload PDFs and view/delete processed invoices.

This repo is suitable to demo:

- Practical OCR + text parsing.
- Clean separation between parsing, persistence, and UI.
- Integration with Oracle and a small but realistic schema.

---

## 1. Tech Stack

- **Language**: Python 3
- **Backend / CLI**: Plain Python scripts (`src/main.py` etc.)
- **Web**: Flask (`src/web_app.py`)
- **OCR**:
  - `pdf2image` + Poppler (for PDF → image)
  - `pytesseract` + Tesseract OCR
- **DB**: Oracle XE (thin driver `oracledb`)
- **Frontend styling**: Tailwind CSS (CDN) in Jinja templates

---

## 2. Folder Structure

High‑level layout:

- `src/`
  - `ocr_engine.py` – low‑level OCR for images and PDFs.
  - `text_parser.py` – robust line‑item extraction from OCR text.
  - `invoice_parser.py` – parses invoice header fields from OCR text.
  - `main.py` – batch/imperative pipeline: OCR → parse → DB insert.
  - `db.py` – Oracle connection factory.
  - `invoice_repository.py` – DB access for `invoices` table.
  - `invoice_items_repository.py` – DB access for `invoice_items` table.
  - `supplier_repository.py` – DB access for `suppliers` (get‑or‑create).
  - `customer_repository.py` – DB access for `customers` (get‑or‑create).
  - `web_app.py` – Flask dashboard (upload & browsing).
  - `test_line_items.py` – small script to debug line item extraction.
- `data/`
  - `invoices/` – raw invoice PDFs (input).
  - `output/` – OCR text + JSON per invoice (debug / inspection).
- `templates/`
  - `base.html` – shared layout (sidebar + top bar).
  - `dashboard.html` – main dashboard (upload, metrics, tables).

---

## 3. Database Design (High Level)

Core tables you work with:

- **`SUPPLIERS`**
  - `supplier_id` (PK, identity)
  - `name`, `address`, `email`, `phone`, `created_at`
  - One row per vendor (e.g. NOVITECH PRIVATE LIMITED).

- **`CUSTOMERS`**
  - `customer_id` (PK, identity)
  - `name`, `billing_address`, `shipping_address`, `created_at`
  - One row per customer (e.g. SRI LANKA TELECOM PLC).

- **`INVOICES`**
  - `invoice_number` (PK)
  - `invoice_d` (DATE)
  - `status` (`UNPAID`, `PAID`, etc.)
  - Monetary: `subtotal`, `discount`, `tax_rate`, `total_tax`, `balance_due`, `total_amount`
  - `currency`
  - Foreign keys: `supplier_id` → `SUPPLIERS`, `customer_id` → `CUSTOMERS`
  - Payment: `payment_terms`, `bank_name`, `branch`, `account_number`, `payment_instructions`
  - `created_at`

- **`INVOICE_ITEMS`**
  - `item_id` (PK, identity)
  - `invoice_number` (FK → `INVOICES.invoice_number`)
  - `description`, `quantity`, `unit_price`, `line_total`, `created_at`

This maps cleanly onto the typical invoice domains you’d expect to discuss in an interview:

- normalized vendor and customer tables;
- a single header row per invoice with all financials;
- 1‑to‑many relationship between invoice headers and line items.

---

## 4. How the Processing Pipeline Works

End‑to‑end flow, both for CLI and web:

1. **User provides a PDF**
   - CLI: place PDFs under `data/invoices/` and run `python -m src.main`.
   - Web: click “Upload invoice PDF” in the dashboard and choose a PDF.

2. **OCR step – `src/ocr_engine.py`**
   - For PDFs:
     - `convert_from_path` turns each page into a PIL image (using Poppler).
     - Each page image is preprocessed (grayscale + autocontrast).
     - `pytesseract.image_to_string` extracts text.
     - All page texts are concatenated into a single string.
   - For images:
     - Reads the file as a PIL image and runs Tesseract directly.

3. **Header parsing – `src/invoice_parser.py`**
   - `parse_invoice_text(text)` normalizes whitespace and uses regex heuristics to extract:
     - Identification: `invoice_number`, `invoice_date`, `invoice_status`.
     - Monetary totals: `subtotal`, `discount`, `tax_rate`, `total_tax`, `balance_due`, `total_amount`, `currency`.
     - Supplier: `supplier_name` (e.g. NOVITECH PRIVATE LIMITED).
     - Customer: `customer_name` (e.g. SRI LANKA TELECOM PLC).
     - Payment & bank: `payment_terms`, `bank_name`, `branch`, `account_number`, `payment_instructions`.
   - The parsed fields are stored in an `InvoiceFields` dataclass and exported to a dict.
   - A JSON snapshot with these fields is written to `data/output/<file>.pdf.json` for transparency/debugging.

4. **Line item parsing – `src/text_parser.py` / `src/invoice_parser.py`**
   - Table‑aware logic:
     - Locates the header line (`Description  Qty  Unit Price  Total`).
     - Reads only lines after the header and stops at `Subtotal` / `Total Tax` / `Balance Due`.
     - Treats the last two monetary values in a line as `unit_price` and `line_total`.
     - Combines split descriptions across lines when necessary (e.g. long training description).
     - Defaults `quantity` to 1 when OCR doesn’t show an explicit column.
   - Result is a list of dicts with: `description`, `quantity`, `unit_price`, `line_total`.

5. **Persistence – `src/main.py` + repositories**
   - `process_file(path, output_dir)` orchestrates:
     1. OCRs the PDF to text and writes `<file>.txt`.
     2. Runs `parse_invoice_text` → `InvoiceFields`.
     3. Cleans the `invoice_number` and falls back to file stem if missing.
     4. Resolves or creates:
        - `supplier_id` via `supplier_repository.get_or_create_supplier`.
        - `customer_id` via `customer_repository.get_or_create_customer`.
     5. Writes the invoice header via `invoice_repository.insert_invoice`.
     6. Extracts line items via `extract_line_items(text)` and writes them using `invoice_items_repository.insert_line_items`.
     7. Returns the final `invoice_number` (used by the web UI to focus the new invoice).

6. **Web flow – `src/web_app.py` + templates**
   - `/` (GET):
     - Uses `get_recent_invoices` to fetch latest invoices (with supplier & customer names).
     - If `?invoice=<number>` is present, also fetches:
       - Detailed header (`get_invoice_by_number`), and
       - Line items (`get_items_for_invoice`),
       and shows them in the right‑hand detail panel.
   - `/upload` (POST):
     - Saves the uploaded PDF into `data/invoices/`.
     - Calls `process_file` to drive OCR + parsing + DB inserts.
     - Uses Flask `flash` for success/error messages.
     - Redirects back to `/` with `?invoice=<number>` so the new invoice is selected.
   - `/invoice/<invoice_number>/delete` (POST):
     - Deletes all line items and the invoice header from the DB.

---

## 5. How to Run (for Interview Demo)

### 5.1. Prerequisites

- **Python 3.x** with `venv`.
- **Oracle XE** running locally, with a user (e.g. `SYSTEM`) that owns:
  - `SUPPLIERS`, `CUSTOMERS`, `INVOICES`, `INVOICE_ITEMS`.
- **Tesseract** and **Poppler** installed and on `PATH`.
- Python deps installed in your virtualenv:

```bash
pip install flask oracledb pdf2image pillow pytesseract
```

Update `src/db.py` with your real Oracle credentials.

### 5.2. Batch (CLI) mode

1. Drop PDFs into `data/invoices/`.
2. Run:

```bash
python -m src.main
```

3. Inspect:

```sql
SELECT * FROM suppliers;
SELECT * FROM customers;
SELECT * FROM invoices;
SELECT * FROM invoice_items;
```

### 5.3. Web dashboard mode

1. Start Flask:

```bash
python -m src.web_app
```

2. Open `http://127.0.0.1:5000/` in your browser.
3. Upload a PDF:
   - The card shows the file name and progress state.
   - The recent invoices table updates.
   - Clicking an invoice shows header details, party info, payment details, and line items.

---

## 6. Talking Points for an Interview

- **Architecture**:
  - Clear separation: OCR engine, parsing, repositories, and web presentation.
  - Use of dataclasses (`InvoiceFields`) to keep parsing logic structured.
  - Repository pattern for all DB access, making it testable and replaceable.

- **Data modeling**:
  - Normalized supplier and customer tables.
  - Clear header/line structure for invoices.
  - Carefully typed numeric columns and string fields that align with business concepts.

- **Parsing strategy**:
  - Heuristic, regex‑based parsing over OCR text.
  - Table‑aware line item extraction rather than naive “any line with numbers”.
  - Defensive defaults and JSON snapshots to aid debugging.

- **UX / UI**:
  - Modern dark dashboard using Tailwind CSS.
  - Focused flows: upload → auto‑select new invoice → see parsed data immediately.
  - Clear feedback via file name preview, progress text, and flash messages.

You can use this README as a walkthrough for interviewers to show you understand both the business problem (invoices into ERP) and the implementation details (OCR, parsing, DB, and web UI). 


# oracle-erp-invoice-ocr
