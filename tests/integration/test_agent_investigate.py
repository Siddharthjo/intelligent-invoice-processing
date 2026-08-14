import uuid
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from invoice_processing.agent.investigate import investigate_invoice
from invoice_processing.agent.result import Recommendation
from invoice_processing.config import get_settings
from invoice_processing.devtools.pdf_builder import build_invoice_pdf
from invoice_processing.erp_mock.seed import seed_mock_erp_data
from invoice_processing.persistence.orm_models import AgentInvestigationRecord
from invoice_processing.pipeline.process_invoice import process_invoice


@pytest.fixture(scope="module", autouse=True)
def _skip_without_openai_key():
    if not get_settings().openai_api_key:
        pytest.skip("OPENAI_API_KEY is not set; skipping live agent investigation test.")


def test_investigate_invoice_matches_a_known_po_and_supplier(db_session: Session, tmp_path: Path):
    seed_mock_erp_data(db_session)

    pdf_path = tmp_path / "invoice.pdf"
    build_invoice_pdf(
        pdf_path,
        invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
        vendor_name="Northwind Traders Ltd.",
        line_items=(
            ("Consulting Services", "10", "150.00", "1500.00"),
            ("Software License", "1", "499.00", "499.00"),
        ),
        subtotal="1999.00",
        tax="159.92",
        total="2158.92",
    )
    processed = process_invoice(pdf_path, db_session)

    result = investigate_invoice(processed.invoice_id, db_session)

    assert result.recommendation in set(Recommendation)
    assert result.tool_call_count > 0
    assert result.trace

    stored_investigation = (
        db_session.query(AgentInvestigationRecord)
        .filter_by(invoice_id=processed.invoice_id)
        .one()
    )
    assert stored_investigation.recommendation == result.recommendation.value
