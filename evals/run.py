from evals.report import print_report, write_json_report
from evals.runner import run_all_cases
from invoice_processing.config import get_settings
from invoice_processing.persistence.db import SessionLocal


def main() -> None:
    model = get_settings().agent_model

    session = SessionLocal()
    try:
        results = run_all_cases(session)
    finally:
        session.close()

    print_report(results, model=model)
    path = write_json_report(results, model=model)
    print(f"\nJSON report written to {path}")


if __name__ == "__main__":
    main()
