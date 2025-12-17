## ERP Invoice OCR – Interview Notes & Deep Dive

This document is meant to help you **explain the project in an interview**. It focuses on the reasoning, trade‑offs, and how everything fits together, rather than just code.

---

## 1. Problem the Project Solves

**Business goal**: Take ERP‑style invoices that arrive as PDFs, and:

- Extract all **key financial and business fields**:
  - Invoice number, date, status, currency.
  - Supplier and customer information.
  - Payment terms, bank and account details.
  - Line items (description, quantity, unit price, totals).
  - Subtotals, tax, discounts, and balance due.
- Store them in a **relational database** (Oracle) in a structure suitable for ERP/BI.
- Provide a **simple web UI** for non‑technical users to upload PDFs and inspect stored invoices.

This is very close to what many real ERP / finance teams need: a bridge from unstructured PDFs to structured, queryable data.

---

## 2. High‑Level Architecture

Think of it as four layers:

1. **Capture layer (OCR)** – `ocr_engine.py`
   - Converts PDFs to images (Poppler + `pdf2image`).
   - Runs Tesseract to extract raw text.
   - Applies minimal preprocessing for better OCR accuracy (grayscale, autocontrast).

2. **Parsing layer (text → structured)** – `invoice_parser.py`, `text_parser.py`
   - **Header parser**:
     - Uses regular expressions and heuristics to find fields like invoice number, dates, totals, and payment details.
     - Aggregates them into a single `InvoiceFields` dataclass.
   - **Line‑item parser**:
     - Recognizes the table header row (Description / Qty / Unit Price / Total).
     - Processes only lines in the table region, not addresses or footers.
     - Ensures lines have the correct numeric patterns before accepting them as items.

3. **Persistence layer (DB access)** – repositories
   - `invoice_repository.py`, `invoice_items_repository.py`, `supplier_repository.py`, `customer_repository.py`.
   - Encapsulate all SQL:
     - Insert/update of invoices, line items, suppliers, customers.
     - Read operations for dashboard (recent invoices, line items, detailed header).
   - Use clean interfaces that accept and return Python dicts, keeping services decoupled from SQL details.

4. **Presentation layer (UI/API)** – `main.py` and `web_app.py`
   - **`main.py`**: CLI batch processor, good for cron jobs or one‑off imports.
   - **`web_app.py` + templates**: Flask app serving a dashboard UI that allows uploads and browsing of processed invoices.

This layering is a strong talking point: each piece has a single responsibility and is testable in isolation.

---

## 3. Detailed Flow of a Single Invoice

### 3.1. From PDF to text

1. User uploads `print.pdf` via the dashboard or drops it into `data/invoices`.
2. `process_file()` determines file type (`.pdf`) and calls:
   - `extract_text_from_pdf()` in `ocr_engine.py`.
3. `ocr_engine`:
   - Uses `convert_from_path(pdf_path, dpi=300, poppler_path=...)` to rasterize each page.
   - For each page (PIL image):
     - `_preprocess_image()` converts to grayscale and auto‑adjusts contrast.
     - `pytesseract.image_to_string(processed_image)` extracts text.
   - Concatenates text for all pages into a single string.
   - Writes it to `data/output/print.pdf.txt` for auditing.

### 3.2. From text to `InvoiceFields`

4. `parse_invoice_text(text)` normalizes whitespace and applies multiple regex patterns:

   - **Identity**:
     - `invoice_number`: finds sequences like `INVOICENO. | SEP25-TRN-ORC-INVO1`.
     - `invoice_date`: from `DATE 25/9/2025`.
     - `invoice_status`: defaults to `UNPAID` unless “Paid / Overdue / Cancelled” is seen.

   - **Totals**:
     - `subtotal`: from `SUBTOTAL 135,000.00`.
     - `discount`: from a `DISCOUNT` line (e.g., "DISCOUNT -", treated as `0`).
     - `tax_rate`: from `TAX RATE 0.00%`.
     - `total_tax`: from `TOTAL TAX 0.00`.
     - `balance_due`: from `Balance Due 135,000.00`.
     - `total_amount`: equal to `balance_due` in this example.
     - `currency`: from `TOTAL (Rs.)` → `Rs.`.

   - **Supplier (vendor)**:
     - `supplier_name`: e.g., `NOVITECH PRIVATE LIMITED`.
     - `supplier_address`, `email`, `phone` are optional and can be filled when present in other samples.

   - **Customer**:
     - `customer_name`: e.g., `SRI LANKA TELECOM PLC`.

   - **Payment / bank**:
     - `payment_terms`: “within 14 business days” or “14 Days”.
     - `bank_name`: `Sampath Bank`.
     - `branch`: `Attidiya`.
     - `account_number`: `008910004000`.
     - `payment_instructions`: “Payment to be transferred directly to Supplier's …”.

5. These get packaged into an `InvoiceFields` dataclass, then exported to a dict and to JSON:

   - `data/output/print.pdf.json` is exactly what you referenced in your message and is deliberately human‑readable for debugging and demos.

### 3.3. From `InvoiceFields` to normalized DB rows

6. Supplier and customer resolution:

   - `supplier_repository.get_or_create_supplier(fields_dict)`:
     - Checks `SUPPLIERS` for a supplier with the same name (and email).
     - Inserts one if not found.
     - Returns `supplier_id`.

   - `customer_repository.get_or_create_customer(fields_dict)`:
     - Checks `CUSTOMERS` by name and billing address.
     - Inserts a row if necessary.
     - Returns `customer_id`.

7. Invoice header insert:

   - `invoice_repository.insert_invoice(fields_dict)`:
     - Converts numeric strings like `"135,000.00"` and `"0.00%"` to numbers.
     - Populates the `INVOICES` row:
       - `invoice_number`, `invoice_d`, `status`.
       - `subtotal`, `discount`, `tax_rate`, `total_tax`, `balance_due`, `total_amount`, `currency`.
       - `supplier_id`, `customer_id`.
       - `payment_terms`, `bank_name`, `branch`, `account_number`, `payment_instructions`.

8. Line items:

   - `text_parser.extract_line_items(text)`:
     - Locates the “Description / Qty / Unit Price / Total” header.
     - Extracts the training line with:
       - Description: **Oracle End User Training on Fixed Asset Module Invoice (September‑2025)**.
       - `quantity = 1`, `unit_price = 135000`, `line_total = 135000`.

   - `invoice_items_repository.insert_line_items(invoice_number, items)` creates rows in `INVOICE_ITEMS`.

---

## 4. Web UI & UX Design Decisions

### 4.1. Dashboard layout

- **Left sidebar** (`base.html`):
  - Brand and short description: “ERP Invoice OCR – Upload, extract & persist invoices”.
  - Space for future navigation (e.g. reports, settings).

- **Top bar**:
  - “Dashboard” title and subtitle.
  - Clear context: “Process PDFs and review extracted invoice data”.

- **Main content** (`dashboard.html`):

  1. **Upload card**:
     - Drag‑and‑drop styled file picker.
     - Shows current file name (“Selected: …”) after selection.
     - Changes button label to “Uploading & processing…” during submit.
     - Uses flash messages to display success/failure after round‑trip.

  2. **KPI cards**:
     - Number of invoices.
     - Latest currency, subtotal, and balance due.

  3. **Recent invoices table**:
     - Columns: Invoice #, Date, Subtotal, Tax, Balance, Total.
     - Entire row cells are clickable to select an invoice.
     - A **Delete** button on the right to remove an invoice and its items.

  4. **Invoice details panel**:
     - Shows:
       - Invoice number, status, and date.
       - Supplier and customer names (plus optional addresses).
       - Payment terms, bank, branch, and account number.
       - Subtotal, discount, tax, total, and balance.
       - Payment instructions.
     - Below that, lists line items (description, quantity, unit price, line total).

This UI looks modern because of Tailwind styling (rounded cards, dark theme, subtle borders, hover states) and because it keeps the key flows very focused: upload, confirm, and inspect data.

---

## 5. Error Handling and Robustness

- **OCR / parsing errors**:
  - If parsing fails to find any meaningful header fields, the pipeline logs a message and skips DB insertion.
  - Web uploads display a flash message like:
    - “Processed file.pdf, but could not detect any invoice data.”

- **DB insertion errors**:
  - Repositories wrap inserts in try/except:
    - On error, they rollback and print a clear error message.
  - Web endpoints also catch exceptions and surface them as flash messages.

- **Duplicate invoices**:
  - `invoice_number` is a primary key, so re‑uploading the same invoice will raise `ORA‑00001`.
  - The UI will show a clear failure message. In a real system you might choose to “upsert” (update existing) instead.

---

## 6. How to Present This in an Interview

When asked to describe the project:

1. **Start with the business story**:
   - “This project takes raw invoice PDFs from an ERP context and converts them into fully structured data in Oracle, including suppliers, customers, payment terms, and line items.”

2. **Walk through one invoice**:
   - PDF → OCR → header parse → line items → database rows.
   - Mention that you store a JSON snapshot (`print.pdf.json`) for transparency.

3. **Highlight design decisions**:
   - Dataclasses (`InvoiceFields`) to keep parsing results explicit and typed.
   - Repository pattern for database isolation and maintainability.
   - Heuristic parsing that is robust to OCR noise, especially around the line‑item table.

4. **Discuss limitations and extensions**:
   - Regex heuristics are tuned to a particular layout; in production, you’d:
     - Add configuration per vendor template, or
     - Use ML/vision models to segment the invoice.
   - Could add:
     - Vendor‑specific parsing profiles.
     - A review/approval workflow in the UI.
     - Export to CSV or integration with a real ERP system.

If you keep these points in mind, you’ll be able to explain not just what the code does, but why it’s designed the way it is—and how you’d evolve it in a real environment. 


