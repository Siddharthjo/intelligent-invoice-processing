from pathlib import Path

import pytest

from tests.support import build_invoice_pdf


@pytest.fixture
def sample_invoice_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "sample_invoice.pdf"
    build_invoice_pdf(pdf_path)
    return pdf_path
