from pathlib import Path
from types import SimpleNamespace

import pytest

from src.extraction.errors import ExtractionError
from src.extraction.extractor import DocumentExtractor


def _response(document, stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=None,
        parsed_output=document,
        model="claude-test",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


def _stub_client(response):
    return SimpleNamespace(messages=SimpleNamespace(parse=lambda **kwargs: response))


@pytest.fixture
def photo(tmp_path):
    path = tmp_path / "page.jpg"
    path.write_bytes(b"fake-jpeg-bytes")
    return path


def test_extract_returns_result(photo, make_document):
    doc = make_document()
    extractor = DocumentExtractor(client=_stub_client(_response(doc)))

    result = extractor.extract([photo])

    assert result.document is doc
    assert result.model == "claude-test"
    assert (result.input_tokens, result.output_tokens) == (10, 5)


def test_extract_runs_injected_validators(photo, make_document):
    bad = make_document(
        prix_forfait=480.0,
        chapitres=[{"titre": "", "lignes": [], "prix_forfait": 480.0}],
    )
    extractor = DocumentExtractor(client=_stub_client(_response(bad)))

    with pytest.raises(ExtractionError, match="Lump-sum conflict"):
        extractor.extract([photo])


def test_extract_with_no_validators_lets_the_same_document_through(photo, make_document):
    bad = make_document(
        prix_forfait=480.0,
        chapitres=[{"titre": "", "lignes": [], "prix_forfait": 480.0}],
    )
    extractor = DocumentExtractor(client=_stub_client(_response(bad)), validators=())

    assert extractor.extract([photo]).document is bad


def test_refusal_is_an_extraction_error(photo, make_document):
    extractor = DocumentExtractor(
        client=_stub_client(_response(make_document(), stop_reason="refusal"))
    )
    with pytest.raises(ExtractionError, match="refused"):
        extractor.extract([photo])


def test_missing_photo_is_reported_before_any_api_call():
    extractor = DocumentExtractor(client=_stub_client(None))
    with pytest.raises(FileNotFoundError):
        extractor.extract([Path("does/not/exist.jpg")])


def test_empty_photo_list_is_rejected():
    extractor = DocumentExtractor(client=_stub_client(None))
    with pytest.raises(ValueError):
        extractor.extract([])
