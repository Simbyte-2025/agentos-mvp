"""Tests for PermissionValidator multi-mode support."""

import pytest
from agentos.security.permissions import PermissionDecision, PermissionMode, PermissionValidator


PROFILES = {
    "agent_a": {
        "permissions": [
            {"tool": "read_file", "actions": ["read"]},
        ],
        "forbidden": [
            {"tool": "*", "actions": ["execute"]},
        ],
    },
    "agent_b": {
        "always_allow": [
            {"tool": "http_fetch", "actions": ["read"]},
        ],
        "always_deny": [
            {"tool": "run_command", "actions": ["execute"]},
        ],
        "always_ask": [
            {"tool": "write_file", "actions": ["write"]},
        ],
    },
}


class TestPermissionModes:
    def test_strict_mode_denies_unmatched(self):
        v = PermissionValidator(PROFILES, mode="strict")
        d = v.validate_tool_access("agent_a", "unknown_tool", "read")
        assert d.allowed is False
        assert d.behavior == "deny"

    def test_permissive_mode_allows_unmatched(self):
        v = PermissionValidator(PROFILES, mode="permissive")
        d = v.validate_tool_access("agent_a", "unknown_tool", "read")
        assert d.allowed is True
        assert d.behavior == "allow"

    def test_interactive_mode_asks_unmatched(self):
        v = PermissionValidator(PROFILES, mode="interactive")
        d = v.validate_tool_access("agent_a", "unknown_tool", "read")
        assert d.allowed is False
        assert d.behavior == "ask"

    def test_forbidden_always_denies_regardless_of_mode(self):
        for mode in PermissionMode:
            v = PermissionValidator(PROFILES, mode=mode)
            d = v.validate_tool_access("agent_a", "run_command", "execute")
            assert d.allowed is False
            assert d.behavior == "deny"

    def test_explicit_permission_always_allows(self):
        for mode in PermissionMode:
            v = PermissionValidator(PROFILES, mode=mode)
            d = v.validate_tool_access("agent_a", "read_file", "read")
            assert d.allowed is True
            assert d.behavior == "allow"


class TestNewRuleKeys:
    def test_always_allow(self):
        v = PermissionValidator(PROFILES, mode="strict")
        d = v.validate_tool_access("agent_b", "http_fetch", "read")
        assert d.allowed is True

    def test_always_deny(self):
        v = PermissionValidator(PROFILES, mode="permissive")
        d = v.validate_tool_access("agent_b", "run_command", "execute")
        assert d.allowed is False
        assert d.behavior == "deny"

    def test_always_ask(self):
        v = PermissionValidator(PROFILES, mode="strict")
        d = v.validate_tool_access("agent_b", "write_file", "write")
        assert d.allowed is False
        assert d.behavior == "ask"


class TestSetMode:
    def test_set_mode_string(self):
        v = PermissionValidator(PROFILES)
        assert v.mode == PermissionMode.STRICT
        v.set_mode("permissive")
        assert v.mode == PermissionMode.PERMISSIVE

    def test_set_mode_enum(self):
        v = PermissionValidator(PROFILES)
        v.set_mode(PermissionMode.INTERACTIVE)
        assert v.mode == PermissionMode.INTERACTIVE


class TestUnknownProfile:
    def test_unknown_profile_denied(self):
        v = PermissionValidator(PROFILES)
        d = v.validate_tool_access("nonexistent", "read_file", "read")
        assert d.allowed is False
        assert d.behavior == "deny"
