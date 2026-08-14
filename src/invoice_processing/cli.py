import argparse
import sys
from pathlib import Path

from invoice_processing.extraction.base import ExtractionError
from invoice_processing.parsing.mapper import MappingError
from invoice_processing.persistence.db import SessionLocal
from invoice_processing.pipeline.process_invoice import process_invoice


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process a single PDF invoice through extraction, validation, and persistence."
    )
    parser.add_argument("pdf_path", type=Path)
    args = parser.parse_args()

    if not args.pdf_path.exists():
        print(f"File not found: {args.pdf_path}", file=sys.stderr)
        raise SystemExit(1)

    session = SessionLocal()
    try:
        result = process_invoice(args.pdf_path, session)
    except (ExtractionError, MappingError) as exc:
        print(f"Failed to process invoice: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        session.close()

    print(
        f"Saved invoice {result.invoice_id} "
        f"(status={result.invoice.status.value}, decision_status={result.decision_status.value})"
    )
    if result.validation_result.issues:
        print("Validation issues:")
        for issue in result.validation_result.issues:
            print(f"  [{issue.severity.value}] {issue.rule_code}: {issue.message}")


if __name__ == "__main__":
    main()
