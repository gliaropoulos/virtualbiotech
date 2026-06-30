"""Tests for the explorer CLI's pure helpers + server registry consistency."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("explore", ROOT / "scripts" / "explore.py")
explore = importlib.util.module_from_spec(_spec)
sys.modules["explore"] = explore
_spec.loader.exec_module(explore)


def test_coerce_types():
    assert explore._coerce("true") is True
    assert explore._coerce("False") is False
    assert explore._coerce("none") is None
    assert explore._coerce("42") == 42
    assert explore._coerce("3.14") == 3.14
    assert explore._coerce("NCT06137183") == "NCT06137183"   # stays a string


def test_parse_kwargs():
    kw = explore.parse_kwargs(["nct_id=NCT06137183", "limit=5", "flag=true"])
    assert kw == {"nct_id": "NCT06137183", "limit": 5, "flag": True}


def test_parse_kwargs_rejects_bare_arg():
    import pytest
    with pytest.raises(SystemExit):
        explore.parse_kwargs(["notakeyvalue"])


def test_server_registry_matches_implemented_servers():
    # Every server in the explorer must be a real importable package with a FastMCP `mcp` object.
    import importlib
    for name, path in explore.SERVERS.items():
        mod = importlib.import_module(path)
        assert mod.mcp.name == name


def test_all_eleven_servers_listed():
    assert len(explore.SERVERS) == 11
