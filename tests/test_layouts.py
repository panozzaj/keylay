"""Tests for layout processing."""

import pytest

from keylay.layouts import (
    DEFAULT_LAYOUT,
    MODIFICATIONS_COMMENT,
    from_layout,
    from_named_layout,
    get_kcm_path,
    parse_map_key,
)


class TestParseMapKey:
    def test_simple_map_key(self):
        result = parse_map_key("map key 58 CTRL_LEFT")
        assert result == (False, "58", "CTRL_LEFT")

    def test_usage_map_key(self):
        result = parse_map_key("map key usage 0x0007002a SHIFT_LEFT")
        assert result == (True, "0x0007002a", "SHIFT_LEFT")

    def test_non_map_line(self):
        assert parse_map_key("type OVERLAY") is None
        assert parse_map_key("# comment") is None
        assert parse_map_key("") is None

    def test_invalid_map_line(self):
        assert parse_map_key("map key") is None
        assert parse_map_key("map foo 58 CTRL") is None


class TestFromLayout:
    def test_empty_mappings_returns_original(self):
        layout = "type OVERLAY\n"
        result = from_layout(layout, {})
        assert result == layout

    def test_adds_new_mapping(self):
        layout = "type OVERLAY\n"
        result = from_layout(layout, {"58": "CTRL_LEFT"})
        assert "map key 58 CTRL_LEFT" in result
        assert MODIFICATIONS_COMMENT.strip() in result

    def test_comments_out_conflicting_mapping(self):
        layout = "type OVERLAY\nmap key 58 CAPS_LOCK\n"
        result = from_layout(layout, {"58": "CTRL_LEFT"})
        assert "# map key 58 CAPS_LOCK" in result
        assert "map key 58 CTRL_LEFT" in result

    def test_removes_duplicate_mapping(self):
        layout = "type OVERLAY\nmap key 58 CAPS_LOCK\n"
        result = from_layout(layout, {"58": "CAPS_LOCK"})
        # Same mapping shouldn't be added twice
        assert result.count("map key 58 CAPS_LOCK") == 1

    def test_multiple_mappings(self):
        layout = "type OVERLAY\n"
        result = from_layout(layout, {"58": "CTRL_LEFT", "29": "CAPS_LOCK"})
        assert "map key 58 CTRL_LEFT" in result
        assert "map key 29 CAPS_LOCK" in result


class TestFromNamedLayout:
    def test_with_no_base_layout(self):
        result = from_named_layout(None, {})
        assert result == DEFAULT_LAYOUT

    def test_with_nonexistent_layout(self):
        result = from_named_layout("nonexistent.kcm", {})
        assert result == DEFAULT_LAYOUT

    def test_with_mappings_no_base(self):
        result = from_named_layout(None, {"58": "CTRL_LEFT"})
        assert "type OVERLAY" in result
        assert "map key 58 CTRL_LEFT" in result


class TestPathTraversal:
    """Test that path traversal attacks are blocked."""

    def test_rejects_parent_directory(self):
        with pytest.raises(ValueError, match="Invalid layout name"):
            get_kcm_path("../keylay_key.pem")

    def test_rejects_absolute_path(self):
        with pytest.raises(ValueError, match="Invalid layout name"):
            get_kcm_path("/etc/passwd")

    def test_rejects_backslash(self):
        with pytest.raises(ValueError, match="Invalid layout name"):
            get_kcm_path("..\\keylay_key.pem")

    def test_accepts_valid_filename(self):
        # Should not raise
        path = get_kcm_path("keyboard_layout_german.kcm")
        assert path.name == "keyboard_layout_german.kcm"
