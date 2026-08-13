import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from invoice_processing.agent.tools import TOOL_HANDLERS, ToolContext
from invoice_processing.erp_mock.seed import seed_mock_erp_data
from invoice_processing.pipeline.process_invoice import process_invoice
from tests.support import build_invoice_pdf


def test_get_supplier_found_and_not_found(db_session: Session):
    seed_mock_erp_data(db_session)
    context = ToolContext(session=db_session, invoice_id=None, raw_text="")

    found = TOOL_HANDLERS["get_supplier"]({"name": "northwind traders ltd."}, context)
    assert found["found"] is True
    assert found["supplier"]["status"] == "active"

    missing = TOOL_HANDLERS["get_supplier"]({"name": "Nonexistent Vendor Co."}, context)
    assert missing == {"found": False}


def test_get_purchase_order_found_and_not_found(db_session: Session):
    seed_mock_erp_data(db_session)
    context = ToolContext(
        session=db_session,
        invoice_id=None,
        raw_text="Invoice text referencing PO-1001 and also PO-DOES-NOT-EXIST as candidates.",
    )

    found = TOOL_HANDLERS["get_purchase_order"]({"po_number": "po-1001"}, context)
    assert found["found"] is True
    assert found["purchase_order"]["vendor_name"] == "Northwind Traders Ltd."

    # Present in the raw text (so it clears the grounding guard), but genuinely not in the ERP data.
    missing = TOOL_HANDLERS["get_purchase_order"]({"po_number": "PO-DOES-NOT-EXIST"}, context)
    assert missing == {"found": False}


def test_get_purchase_order_rejects_a_po_number_not_present_in_raw_text(db_session: Session):
    seed_mock_erp_data(db_session)
    # PO-1001 genuinely exists in the mock ERP data, but this invoice's raw text never
    # mentions it -- the tool must refuse to look it up rather than let a guess through.
    context = ToolContext(
        session=db_session,
        invoice_id=None,
        raw_text="Some invoice with no purchase order reference anywhere in it.",
    )

    result = TOOL_HANDLERS["get_purchase_order"]({"po_number": "PO-1001"}, context)
    assert result["found"] is False
    assert "rejected_reason" in result


def test_check_duplicate_excludes_the_invoice_under_investigation(db_session: Session, tmp_path: Path):
    invoice_number = f"INV-{uuid.uuid4().hex[:8]}"
    vendor_name = "Duplicate Check Co."

    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(pdf_path, invoice_number=invoice_number, vendor_name=vendor_name)
    result = process_invoice(pdf_path, db_session)

    context = ToolContext(session=db_session, invoice_id=result.invoice_id, raw_text="")
    handler = TOOL_HANDLERS["check_duplicate"]

    # Excludes itself: this exact invoice exists, but it IS the one under investigation.
    self_check = handler({"vendor": vendor_name, "invoice_number": invoice_number}, context)
    assert self_check == {"is_duplicate": False, "matching_invoice_id": None}

    # A second, genuinely separate invoice with the same vendor/number IS a duplicate.
    pdf_path_2 = tmp_path / "invoice_2.pdf"
    build_invoice_pdf(pdf_path_2, invoice_number=invoice_number, vendor_name=vendor_name)
    second = process_invoice(pdf_path_2, db_session)

    context_2 = ToolContext(session=db_session, invoice_id=second.invoice_id, raw_text="")
    dup_check = handler({"vendor": vendor_name, "invoice_number": invoice_number}, context_2)
    assert dup_check["is_duplicate"] is True
    assert dup_check["matching_invoice_id"] == str(result.invoice_id)
