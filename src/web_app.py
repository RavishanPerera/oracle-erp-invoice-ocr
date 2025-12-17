from pathlib import Path
from typing import List, Dict, Any

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)

from src.main import process_file, DEFAULT_INVOICE_DIR, DEFAULT_OUTPUT_DIR
from src.invoice_repository import (
    get_recent_invoices,
    get_invoice_by_number,
    delete_invoice,
)
from src.invoice_items_repository import (
    get_items_for_invoice,
    delete_items_for_invoice,
)


BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / DEFAULT_INVOICE_DIR
OUTPUT_DIR = BASE_DIR / DEFAULT_OUTPUT_DIR

# Tell Flask where templates live (project_root/templates)
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))
app.secret_key = "change-this-in-production"


@app.route("/", methods=["GET"])
def dashboard():
    invoices = get_recent_invoices(limit=20)
    selected_invoice_number = request.args.get("invoice")
    selected_items: List[Dict[str, Any]] = []
    invoice_detail: Dict[str, Any] | None = None

    if selected_invoice_number:
        selected_items = get_items_for_invoice(selected_invoice_number)
        invoice_detail = get_invoice_by_number(selected_invoice_number)

    return render_template(
        "dashboard.html",
        invoices=invoices,
        selected_invoice_number=selected_invoice_number,
        selected_items=selected_items,
        invoice_detail=invoice_detail,
    )


@app.route("/upload", methods=["POST"])
def upload_invoice():
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("Please choose a PDF file to upload.", "error")
        return redirect(url_for("dashboard"))

    if not file.filename.lower().endswith(".pdf"):
        flash("Only PDF files are supported.", "error")
        return redirect(url_for("dashboard"))

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Save with original filename; production code may want unique names
    target_path = UPLOAD_DIR / file.filename
    file.save(target_path)

    try:
        invoice_number = process_file(target_path, OUTPUT_DIR)
        if invoice_number:
            flash(f"Successfully processed {file.filename}", "success")
            # Redirect focusing on this specific invoice in the UI
            return redirect(url_for("dashboard", invoice=invoice_number))
        else:
            flash(
                f"Processed {file.filename}, but could not detect any invoice data.",
                "error",
            )
    except Exception as exc:  # pragma: no cover - defensive
        flash(f"Failed to process {file.filename}: {exc}", "error")

    # Fallback redirect if we couldn't determine an invoice number
    return redirect(url_for("dashboard"))


@app.route("/invoice/<invoice_number>/delete", methods=["POST"])
def delete_invoice_route(invoice_number: str):
    """
    Delete an invoice and its line items.
    """
    try:
        delete_items_for_invoice(invoice_number)
        delete_invoice(invoice_number)
        flash(f"Deleted invoice {invoice_number}", "success")
    except Exception as exc:  # pragma: no cover - defensive
        flash(f"Failed to delete invoice {invoice_number}: {exc}", "error")

    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    # For local development
    app.run(debug=True)


