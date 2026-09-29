"""Bounded page planning and deterministic merging for connected extraction."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .schemas import DocumentExtraction, ExtractedLine

MAX_PAGES_PER_BATCH = 5
MAX_TEXT_CHARS_PER_BATCH = 50_000
MAX_DOCUMENT_PAGES = 100
MAX_DOCUMENT_TEXT_CHARS = 200_000

HEADER_FIELDS = (
    "kind",
    "vendor",
    "number",
    "po_number",
    "date",
    "due_date",
    "currency",
    "subtotal",
    "tax",
    "freight",
    "discounts",
    "total",
)


class PageLike(Protocol):
    number: int
    text: str


class ConnectedPageError(ValueError):
    """Safe, actionable page coverage error; messages never include source text."""


class PageLimitError(ConnectedPageError):
    pass


class PageCoverageError(ConnectedPageError):
    pass


class PageConflictError(ConnectedPageError):
    pass


@dataclass(frozen=True)
class PageBatch:
    pages: tuple[PageLike, ...]

    @property
    def page_numbers(self) -> tuple[int, ...]:
        return tuple(page.number for page in self.pages)

    @property
    def prompt_text(self) -> str:
        return "\n\n".join(f"Page {page.number}: {page.text}" for page in self.pages)


class PageExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(ge=1)
    extraction: DocumentExtraction


class PageBatchExtraction(BaseModel):
    """Structured model response for one requested batch."""

    model_config = ConfigDict(extra="forbid")

    pages: list[PageExtraction] = Field(min_length=1, max_length=MAX_PAGES_PER_BATCH)


@dataclass(frozen=True)
class MergedPageExtraction:
    extraction: DocumentExtraction
    field_pages: dict[str, int]
    line_pages: dict[int, int]


def _validate_limits(
    max_pages_per_batch: int,
    max_text_chars: int,
    max_document_pages: int,
    max_document_text_chars: int,
) -> None:
    if not 1 <= max_pages_per_batch <= MAX_PAGES_PER_BATCH:
        raise ValueError(f"max_pages_per_batch must be between 1 and {MAX_PAGES_PER_BATCH}")
    if not 1 <= max_text_chars <= MAX_TEXT_CHARS_PER_BATCH:
        raise ValueError(f"max_text_chars must be between 1 and {MAX_TEXT_CHARS_PER_BATCH}")
    if not 1 <= max_document_pages <= MAX_DOCUMENT_PAGES:
        raise ValueError(f"max_document_pages must be between 1 and {MAX_DOCUMENT_PAGES}")
    if not 1 <= max_document_text_chars <= MAX_DOCUMENT_TEXT_CHARS:
        raise ValueError(f"max_document_text_chars must be between 1 and {MAX_DOCUMENT_TEXT_CHARS}")


def plan_page_batches(
    pages: Sequence[PageLike],
    *,
    max_pages_per_batch: int = MAX_PAGES_PER_BATCH,
    max_text_chars: int = MAX_TEXT_CHARS_PER_BATCH,
    max_document_pages: int = MAX_DOCUMENT_PAGES,
    max_document_text_chars: int = MAX_DOCUMENT_TEXT_CHARS,
) -> tuple[PageBatch, ...]:
    """Cover every source page once, without clipping any page's text."""

    _validate_limits(
        max_pages_per_batch, max_text_chars, max_document_pages, max_document_text_chars
    )
    if not pages:
        raise PageCoverageError("Document has no pages to extract")
    if len(pages) > max_document_pages:
        raise PageLimitError(f"Document exceeds the {max_document_pages}-page extraction limit")

    ordered = sorted(pages, key=lambda page: page.number)
    numbers = tuple(page.number for page in ordered)
    if numbers != tuple(range(1, len(ordered) + 1)):
        raise PageCoverageError(
            "Source page numbers must cover 1 through the last page exactly once"
        )

    batches: list[PageBatch] = []
    current: list[PageLike] = []
    current_chars = 0
    for page in ordered:
        page_chars = len(f"Page {page.number}: {page.text}")
        if page_chars > max_text_chars:
            raise PageLimitError(
                f"Page {page.number} exceeds the {max_text_chars}-character model text limit"
            )
        additional_chars = page_chars + (2 if current else 0)
        if current and (
            len(current) >= max_pages_per_batch or current_chars + additional_chars > max_text_chars
        ):
            batches.append(PageBatch(tuple(current)))
            current = []
            current_chars = 0
            additional_chars = page_chars
        current.append(page)
        current_chars += additional_chars
    if current:
        batches.append(PageBatch(tuple(current)))
    if sum(len(batch.prompt_text) for batch in batches) > max_document_text_chars:
        raise PageLimitError(
            f"Document exceeds the {max_document_text_chars}-character model text budget"
        )
    return tuple(batches)


def validate_batch_response(
    batch: PageBatch, response: PageBatchExtraction | dict[str, Any]
) -> tuple[PageExtraction, ...]:
    """Require one result for each requested page, then restore source-page order."""

    parsed = PageBatchExtraction.model_validate(response)
    expected = batch.page_numbers
    by_page = {result.page_number: result for result in parsed.pages}
    if len(parsed.pages) != len(expected) or set(by_page) != set(expected):
        raise PageCoverageError(
            f"Model response must contain exactly source pages {list(expected)}"
        )
    return tuple(by_page[number] for number in expected)


def merge_page_extractions(
    batches: Sequence[PageBatch],
    responses: Sequence[PageBatchExtraction | dict[str, Any]],
) -> MergedPageExtraction:
    """Merge complete page results; reject contradictory document headers."""

    if not batches or len(batches) != len(responses):
        raise PageCoverageError("Every requested page batch needs one model response")
    numbers = tuple(number for batch in batches for number in batch.page_numbers)
    if numbers != tuple(range(1, len(numbers) + 1)):
        raise PageCoverageError("Page batches must cover source pages in order exactly once")
    if len(numbers) > MAX_DOCUMENT_PAGES or any(
        not 1 <= len(batch.pages) <= MAX_PAGES_PER_BATCH
        or len(batch.prompt_text) > MAX_TEXT_CHARS_PER_BATCH
        for batch in batches
    ):
        raise PageLimitError("Page batches exceed connected extraction limits")
    if sum(len(batch.prompt_text) for batch in batches) > MAX_DOCUMENT_TEXT_CHARS:
        raise PageLimitError("Page batches exceed the connected extraction text budget")

    values: dict[str, str] = {}
    field_pages: dict[str, int] = {}
    lines: list[ExtractedLine] = []
    line_pages: dict[int, int] = {}
    for batch, response in zip(batches, responses, strict=True):
        for page_result in validate_batch_response(batch, response):
            page_number = page_result.page_number
            extraction = page_result.extraction
            for key in HEADER_FIELDS:
                value = getattr(extraction, key)
                if value is None or not value.strip() or (key == "kind" and value == "unknown"):
                    continue
                if key in values and values[key].strip() != value.strip():
                    raise PageConflictError(f"Conflicting {key} values across source pages")
                if key not in values:
                    values[key] = value
                    field_pages[key] = page_number
            for line in extraction.lines:
                line_pages[len(lines)] = page_number
                lines.append(line)

    return MergedPageExtraction(
        extraction=DocumentExtraction.model_validate({**values, "lines": lines}),
        field_pages=field_pages,
        line_pages=line_pages,
    )
