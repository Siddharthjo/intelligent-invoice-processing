from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_invoice_pdf(
    path: Path,
    *,
    invoice_number: str = "INV-1001",
    vendor_name: str = "Acme Supplies Inc.",
    issue_date: str = "2026-01-15",
    due_date: str = "2026-02-14",
    po_number: str | None = None,
    line_items: tuple[tuple[str, str, str, str], ...] = (
        ("Widget A", "2", "10.00", "20.00"),
        ("Widget B", "1", "30.00", "30.00"),
    ),
    subtotal: str = "50.00",
    tax: str = "5.00",
    total: str = "55.00",
) -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=letter)

    header_lines = [
        vendor_name,
        f"Invoice Number: {invoice_number}",
        f"Invoice Date: {issue_date}",
        f"Due Date: {due_date}",
    ]
    if po_number:
        header_lines.append(f"PO Number: {po_number}")
    table_data = [["Description", "Qty", "Unit Price", "Amount"], *line_items]
    footer_lines = [
        f"Subtotal: ${subtotal}",
        f"Tax: ${tax}",
        f"Total: ${total}",
    ]

    table = Table(table_data)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))

    elements = [Paragraph(line, styles["Normal"]) for line in header_lines]
    elements.append(Spacer(1, 12))
    elements.append(table)
    elements.append(Spacer(1, 12))
    elements.extend(Paragraph(line, styles["Normal"]) for line in footer_lines)

    doc.build(elements)
