from agentos.security.permissions import PermissionValidator


def test_permission_validator_allows_read():
    profiles = {
        "p": {
            "permissions": [{"tool": "read_file", "actions": ["read"]}],
            "forbidden": [{"tool": "*", "actions": ["write"]}],
        }
    }
    v = PermissionValidator(profiles)
    assert v.validate_tool_access("p", "read_file", "read").allowed is True


def test_permission_validator_denies_forbidden():
    profiles = {
        "p": {
            "permissions": [{"tool": "*", "actions": ["read", "write"]}],
            "forbidden": [{"tool": "read_file", "actions": ["write"]}],
        }
    }
    v = PermissionValidator(profiles)
    assert v.validate_tool_access("p", "read_file", "write").allowed is False
