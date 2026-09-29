from types import SimpleNamespace

from invoicelens.connected_pages import PageBatchExtraction, PageExtraction
from invoicelens.extraction import (
    EXTRACTION_PROMPT_V2,
    ConnectedExtractionAdapter,
    PageContent,
)
from invoicelens.schemas import DocumentExtraction


def test_connected_adapter_records_usage_without_source_text():
    class FakeModel:
        def invoke(self, messages):
            assert messages[0].content == EXTRACTION_PROMPT_V2
            assert "Invoice #: INV-MODEL-1" in messages[1].content[0]["text"]
            return {
                "parsed": PageBatchExtraction(
                    pages=[
                        PageExtraction(
                            page_number=1,
                            extraction=DocumentExtraction(
                                kind="invoice", number="INV-MODEL-1"
                            ),
                        )
                    ]
                ),
                "raw": SimpleNamespace(
                    usage_metadata={"input_tokens": 91, "output_tokens": 12}
                ),
                "parsing_error": None,
            }

    extractor = ConnectedExtractionAdapter.__new__(ConnectedExtractionAdapter)
    extractor.model = FakeModel()
    result = extractor.extract(
        [PageContent(1, "Invoice #: INV-MODEL-1", "native", 612, 792, [])],
        b"",
        "application/pdf",
    )
    assert result.number == "INV-MODEL-1"
    assert extractor.last_field_pages == {"kind": 1, "number": 1}
    assert extractor.last_usage == {
        "prompt_version": "extraction-v2",
        "input_tokens": 91,
        "output_tokens": 12,
        "cost_status": "unknown",
    }


def test_connected_adapter_covers_later_pages_in_bounded_calls():
    class FakeModel:
        def __init__(self):
            self.batches = []

        def invoke(self, messages):
            blocks = messages[1].content
            numbers = [int(block["text"].split(":", 1)[0][5:]) for block in blocks]
            self.batches.append(numbers)
            return {
                "parsed": PageBatchExtraction(
                    pages=[
                        PageExtraction(
                            page_number=number,
                            extraction=DocumentExtraction(
                                kind="invoice" if number == 1 else "unknown",
                                number="INV-7" if number == 1 else None,
                                total="19.00" if number == 7 else None,
                            ),
                        )
                        for number in numbers
                    ]
                ),
                "raw": SimpleNamespace(
                    usage_metadata={"input_tokens": 10, "output_tokens": 2}
                ),
            }

    extractor = ConnectedExtractionAdapter.__new__(ConnectedExtractionAdapter)
    extractor.model = FakeModel()
    result = extractor.extract(
        [
            PageContent(number, f"Page {number} text", "native", 612, 792, [])
            for number in range(1, 8)
        ],
        b"",
        "application/pdf",
    )
    assert extractor.model.batches == [[1, 2, 3, 4, 5], [6, 7]]
    assert result.total == "19.00"
    assert extractor.last_field_pages["total"] == 7
    assert extractor.last_usage["input_tokens"] == 20
