from enum import StrEnum

from pydantic import BaseModel


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class ValidationIssue(BaseModel):
    rule_code: str
    severity: Severity
    message: str


class ValidationResult(BaseModel):
    issues: list[ValidationIssue] = []

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity == Severity.ERROR for issue in self.issues)
