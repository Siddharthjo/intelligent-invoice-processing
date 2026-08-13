from dataclasses import dataclass, field

from invoice_processing.domain.enums import ExtractionMethod

Table = list[list[str | None]]


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    tables: list[Table] = field(default_factory=list)


@dataclass
class ExtractedDocument:
    source_filename: str
    method: ExtractionMethod
    pages: list[ExtractedPage]

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def full_text(self) -> str:
        return "\n".join(page.text for page in self.pages)

    @property
    def tables(self) -> list[Table]:
        return [table for page in self.pages for table in page.tables]


class ExtractionError(Exception):
    """Raised when no usable text can be extracted from a PDF by any available method."""
