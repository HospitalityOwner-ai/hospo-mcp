"""Tests for server creation and tool registration."""

import pytest
from hospo_mcp.server import create_server
from hospo_mcp.config import config


def test_server_creates_successfully():
    """Server should create without errors."""
    mcp = create_server()
    assert mcp is not None


def test_server_has_correct_name():
    """Server name should match config."""
    mcp = create_server()
    assert mcp.name == "hospo-mcp"


def test_config_mock_mode():
    """Default config should be in mock mode."""
    status = config.integrations_status()
    # In test env without real credentials, everything should be mock
    for integration, info in status.items():
        assert "mock" in info


def test_integration_status_keys():
    """Integration status should include all three integrations."""
    status = config.integrations_status()
    assert "lightspeed" in status
    assert "xero" in status
    assert "deputy" in status
