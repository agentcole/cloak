"""NER detection (spaCy + GLiNER backends). Skipped unless the relevant
optional model is installed, so the core suite stays dependency-free."""

import importlib.util
import os

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


# --- GLiNER backend (the packaged default) ---------------------------------
# Opt-in: GLiNER downloads a model on first use, so this is gated behind an env
# var to keep CI fast. Run locally with CLOAK_TEST_GLINER=1 once the model is
# cached.
_RUN_GLINER = bool(os.environ.get("CLOAK_TEST_GLINER")) and (
    importlib.util.find_spec("gliner") is not None
)


@pytest.mark.skipif(not _RUN_GLINER, reason="set CLOAK_TEST_GLINER=1 with gliner installed")
def test_default_gliner_backend_detects_and_roundtrips():
    from cloak import Cloak, CloakPolicy

    # Default policy: ner_backend='gliner', model 'urchade/gliner_multi_pii-v1'.
    c = Cloak(CloakPolicy(detectors=["regex", "ner"]))
    text = "Jane Doe emailed jane@acme.com from Berlin about the Acme Corp account."
    res = c.mask_text(text)
    assert res.by_type().get("PERSON")
    assert "Jane Doe" not in res.text
    assert c.unmask_text(res.text, res.vault) == text
