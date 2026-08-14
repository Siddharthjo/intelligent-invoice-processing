from invoice_processing.validation.result import Severity, ValidationIssue, ValidationResult


def _issue(step: str, severity: Severity) -> ValidationIssue:
    return ValidationIssue(step=step, rule_code="TEST_CODE", severity=severity, message="test")


def test_no_issues_has_no_severe_failure():
    assert ValidationResult(issues=[]).has_severe_failure is False


def test_v9_error_is_a_severe_failure():
    result = ValidationResult(issues=[_issue("V9", Severity.ERROR)])
    assert result.has_severe_failure is True


def test_v9_warning_is_not_a_severe_failure():
    result = ValidationResult(issues=[_issue("V9", Severity.WARNING)])
    assert result.has_severe_failure is False


def test_error_on_a_non_v9_step_is_not_a_severe_failure():
    # e.g. V1 vendor-not-identified or V5 duplicate: ambiguous enough that an agent
    # investigation is still worthwhile, unlike a V9 arithmetic failure.
    result = ValidationResult(issues=[_issue("V1", Severity.ERROR), _issue("V5", Severity.ERROR)])
    assert result.has_severe_failure is False
