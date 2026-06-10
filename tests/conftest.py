import pytest
from pathlib import Path
from unittest.mock import patch

from backend import config


@pytest.fixture
def vault_path(tmp_path, monkeypatch):
    """Redirect all vault I/O to a fresh temp directory for each test."""
    vault = tmp_path / "TestVault"
    vault.mkdir()
    monkeypatch.setattr(config, "VAULT_PATH", vault)
    return vault
