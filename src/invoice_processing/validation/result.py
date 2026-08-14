from enum import StrEnum

from pydantic import BaseModel


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class ValidationIssue(BaseModel):
    step: str
    rule_code: str
    severity: Severity
    message: str


_SEVERE_FAILURE_STEPS = frozenset({"V9"})


class ValidationResult(BaseModel):
    issues: list[ValidationIssue] = []

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity == Severity.ERROR for issue in self.issues)

    @property
    def has_severe_failure(self) -> bool:
        """True when a failure is severe enough to reject without agent investigation.

        Scoped to V9 (arithmetic/total) errors -- the invoice's own numbers don't
        reconcile, so there's nothing an LLM investigation could usefully judge. Other
        ERROR-severity issues (an unidentified vendor, a duplicate) are ambiguous enough
        that an agent look is still worthwhile.
        """
        return any(
            issue.severity == Severity.ERROR and issue.step in _SEVERE_FAILURE_STEPS
            for issue in self.issues
        )
