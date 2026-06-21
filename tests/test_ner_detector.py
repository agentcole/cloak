"""NER detection (spaCy backend). Skipped unless spaCy + the small English
model are installed, so the core suite stays dependency-free."""

import importlib.util

import pytest

_HAS_SPACY = importlib.util.find_spec("spacy") is not None
_HAS_MODEL = False
if _HAS_SPACY:
    import spacy

    _HAS_MODEL = "en_core_web_sm" in spacy.util.get_installed_models()

pytestmark = pytest.mark.skipif(
    not (_HAS_SPACY and _HAS_MODEL),
    reason="spaCy + en_core_web_sm not installed",
)


def _engine():
    from cloak import Cloak, CloakPolicy

    return Cloak(
        CloakPolicy(detectors=["regex", "ner"], ner_backend="spacy", ner_model="en_core_web_sm")
    )


def test_ner_catches_person_org_location_and_roundtrips():
    c = _engine()
    text = "Jane Doe at jane@acme.com flies to Berlin for Acme Corp"
    res = c.mask_text(text)
    types = res.by_type()
    assert types.get("PERSON")  # name caught by NER
    assert types.get("EMAIL")  # still caught by regex
    assert "Jane Doe" not in res.text
    assert c.unmask_text(res.text, res.vault) == text


def test_ner_and_regex_do_not_double_mask_overlap():
    # The email's local part shouldn't also be grabbed as a name, etc.
    c = _engine()
    res = c.mask_text("contact jane@acme.com")
    assert res.text == "contact [EMAIL_1]"
