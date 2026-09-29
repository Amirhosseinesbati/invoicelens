from dataclasses import dataclass

import pytest
from invoicelens.connected_pages import (
    PageBatchExtraction,
    PageConflictError,
    PageCoverageError,
    PageExtraction,
    PageLimitError,
    merge_page_extractions,
    plan_page_batches,
    validate_batch_response,
)
from invoicelens.schemas import DocumentExtraction, ExtractedLine


@dataclass
class Page:
    number: int
    text: str


def result(page_number: int, **fields) -> PageExtraction:
    return PageExtraction(
        page_number=page_number, extraction=DocumentExtraction(**fields)
    )


def test_plan_covers_every_page_in_bounded_source_order():
    pages = [Page(number, f"text {number}") for number in range(12, 0, -1)]

    batches = plan_page_batches(pages)

    assert [batch.page_numbers for batch in batches] == [
        (1, 2, 3, 4, 5),
        (6, 7, 8, 9, 10),
        (11, 12),
    ]
    assert all(len(batch.prompt_text) <= 50_000 for batch in batches)
    assert "Page 12: text 12" in batches[-1].prompt_text


def test_plan_splits_at_text_budget_without_clipping():
    pages = [Page(1, "A" * 18), Page(2, "B" * 18), Page(3, "")]

    batches = plan_page_batches(pages, max_text_chars=40)

    assert [batch.page_numbers for batch in batches] == [(1,), (2, 3)]
    assert batches[0].prompt_text == "Page 1: " + "A" * 18
    assert batches[1].prompt_text == "Page 2: " + "B" * 18 + "\n\nPage 3: "


def test_plan_rejects_oversized_and_missing_pages():
    with pytest.raises(PageLimitError, match="Page 2 exceeds"):
        plan_page_batches([Page(1, "ok"), Page(2, "X" * 40)], max_text_chars=40)
    with pytest.raises(PageCoverageError, match="exactly once"):
        plan_page_batches([Page(1, "ok"), Page(3, "gap")])
    with pytest.raises(PageCoverageError, match="exactly once"):
        plan_page_batches([Page(1, "one"), Page(1, "duplicate")])
    with pytest.raises(PageLimitError, match="100-page"):
        plan_page_batches([Page(number, "") for number in range(1, 102)])
    with pytest.raises(PageLimitError, match="model text budget"):
        plan_page_batches(
            [Page(1, "A" * 20), Page(2, "B" * 20)], max_document_text_chars=50
        )


@pytest.mark.parametrize("ids", [[1], [1, 1], [1, 3]])
def test_batch_response_rejects_omissions_duplicates_and_extra_pages(ids):
    batch = plan_page_batches([Page(1, "one"), Page(2, "two")])[0]
    response = PageBatchExtraction(pages=[result(number) for number in ids])

    with pytest.raises(PageCoverageError, match="exactly source pages"):
        validate_batch_response(batch, response)


def test_merge_preserves_field_and_line_page_provenance():
    batches = plan_page_batches([Page(1, "one"), Page(2, "two"), Page(3, "three")])
    responses = [
        PageBatchExtraction(
            pages=[
                result(
                    3,
                    kind="invoice",
                    total="20.00",
                    lines=[ExtractedLine(sku="SKU-3", amount="12.00")],
                ),
                result(
                    1,
                    kind="invoice",
                    vendor="Harbor Supply",
                    number="INV-7",
                    lines=[ExtractedLine(sku="SKU-1", amount="8.00")],
                ),
                result(2, kind="invoice", vendor="Harbor Supply"),
            ]
        )
    ]

    merged = merge_page_extractions(batches, responses)

    assert merged.extraction.kind == "invoice"
    assert merged.extraction.vendor == "Harbor Supply"
    assert merged.extraction.total == "20.00"
    assert [line.sku for line in merged.extraction.lines] == ["SKU-1", "SKU-3"]
    assert merged.field_pages == {"kind": 1, "vendor": 1, "number": 1, "total": 3}
    assert merged.line_pages == {0: 1, 1: 3}


def test_merge_rejects_conflicting_headers_and_incomplete_response_set():
    batches = plan_page_batches([Page(1, "one"), Page(2, "two")], max_pages_per_batch=1)
    with pytest.raises(PageCoverageError, match="one model response"):
        merge_page_extractions(batches, [PageBatchExtraction(pages=[result(1)])])
    with pytest.raises(PageConflictError, match="Conflicting total"):
        merge_page_extractions(
            batches,
            [
                PageBatchExtraction(pages=[result(1, total="10.00")]),
                PageBatchExtraction(pages=[result(2, total="11.00")]),
            ],
        )
