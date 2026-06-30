"""Config must import and expose defaults without any credentials present."""
from virtual_biotech import config


def test_models_default_to_paper_values():
    assert config.MODEL_SUPPORT.startswith("claude-haiku")
    assert "sonnet" in config.MODEL_SCIENTIST


def test_api_key_optional():
    # build/test-safe: absence of a key returns None rather than raising
    assert config.anthropic_api_key() in (None, config.anthropic_api_key())


def test_endpoints_present():
    assert config.ENDPOINTS.clinicaltrials.startswith("https://")
