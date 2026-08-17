from enum import StrEnum


class InvoiceStatus(StrEnum):
    PENDING_VALIDATION = "pending_validation"
    VALID = "valid"
    INVALID = "invalid"


class ExtractionMethod(StrEnum):
    TEXT_LAYER = "text_layer"
    OCR = "ocr"


class IntakeSource(StrEnum):
    MANUAL_UPLOAD = "manual_upload"
    GMAIL = "gmail"
