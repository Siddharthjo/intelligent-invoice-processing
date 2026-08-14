from dataclasses import dataclass, field

from invoice_processing.agent.result import Recommendation


@dataclass
class EvalCase:
    name: str
    category: str
    pdf_kwargs: dict = field(default_factory=dict)
    expected_recommendation: Recommendation = Recommendation.HUMAN_REVIEW
    pre_process_duplicate: bool = False


EVAL_CASES: list[EvalCase] = [
    EvalCase(
        name="clean_auto_approve",
        category="auto_approve",
        pdf_kwargs=dict(
            vendor_name="Northwind Traders Ltd.",
            po_number="PO-1001",
            line_items=(
                ("Consulting Services", "10", "150.00", "1500.00"),
                ("Software License", "1", "499.00", "499.00"),
            ),
            subtotal="1999.00",
            tax="159.92",
            total="2158.92",
        ),
        expected_recommendation=Recommendation.AUTO_APPROVE,
    ),
    EvalCase(
        name="unknown_supplier",
        category="unknown_supplier",
        pdf_kwargs=dict(
            vendor_name="Meridian Hardware Supply",
            line_items=(
                ("Steel Brackets", "100", "4.50", "450.00"),
                ("Mounting Kit", "20", "12.75", "255.00"),
            ),
            subtotal="705.00",
            tax="56.40",
            total="761.40",
        ),
        expected_recommendation=Recommendation.HUMAN_REVIEW,
    ),
    EvalCase(
        name="blocked_supplier",
        category="blocked_supplier",
        pdf_kwargs=dict(
            vendor_name="Initech Consulting",
            line_items=(("Advisory Services", "5", "200.00", "1000.00"),),
            subtotal="1000.00",
            tax="80.00",
            total="1080.00",
        ),
        expected_recommendation=Recommendation.HUMAN_REVIEW,
    ),
    EvalCase(
        name="po_mismatch_large",
        category="po_mismatch",
        pdf_kwargs=dict(
            vendor_name="Northwind Traders Ltd.",
            po_number="PO-1001",
            line_items=(("Bulk Order", "1", "6000.00", "6000.00"),),
            subtotal="6000.00",
            tax="480.00",
            total="6480.00",
        ),
        expected_recommendation=Recommendation.HUMAN_REVIEW,
    ),
    EvalCase(
        name="duplicate_invoice",
        category="duplicate",
        pdf_kwargs=dict(
            vendor_name="Southgate Supplies Inc.",
            line_items=(("Office Chairs", "4", "120.00", "480.00"),),
            subtotal="480.00",
            tax="38.40",
            total="518.40",
        ),
        expected_recommendation=Recommendation.RETURN_TO_VENDOR,
        pre_process_duplicate=True,
    ),
    EvalCase(
        name="no_po_reference",
        category="no_po_reference",
        pdf_kwargs=dict(
            vendor_name="Northwind Traders Ltd.",
            line_items=(("Consulting Services", "5", "150.00", "750.00"),),
            subtotal="750.00",
            tax="60.00",
            total="810.00",
        ),
        expected_recommendation=Recommendation.HUMAN_REVIEW,
    ),
    EvalCase(
        name="po_cancelled",
        category="po_status",
        pdf_kwargs=dict(
            vendor_name="Northwind Traders Ltd.",
            po_number="PO-4004",
            line_items=(("Consulting Services", "5", "150.00", "750.00"),),
            subtotal="750.00",
            tax="0.00",
            total="750.00",
        ),
        expected_recommendation=Recommendation.RETURN_TO_VENDOR,
    ),
    EvalCase(
        name="po_closed",
        category="po_status",
        pdf_kwargs=dict(
            vendor_name="Globex Corporation",
            po_number="PO-3003",
            line_items=(("Parts Order", "1", "500.00", "500.00"),),
            subtotal="500.00",
            tax="0.00",
            total="500.00",
        ),
        expected_recommendation=Recommendation.RETURN_TO_VENDOR,
    ),
    EvalCase(
        name="variance_within_tolerance",
        category="borderline",
        pdf_kwargs=dict(
            vendor_name="Southgate Supplies Inc.",
            po_number="PO-2002",
            line_items=(("Office Supplies Bundle", "1", "1299.00", "1299.00"),),
            subtotal="1299.00",
            tax="0.00",
            total="1299.00",
        ),
        expected_recommendation=Recommendation.AUTO_APPROVE,
    ),
    EvalCase(
        name="variance_outside_tolerance",
        category="borderline",
        pdf_kwargs=dict(
            vendor_name="Southgate Supplies Inc.",
            po_number="PO-2002",
            line_items=(("Office Supplies Bundle", "1", "1301.00", "1301.00"),),
            subtotal="1301.00",
            tax="0.00",
            total="1301.00",
        ),
        expected_recommendation=Recommendation.HUMAN_REVIEW,
    ),
]
