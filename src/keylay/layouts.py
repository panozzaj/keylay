"""Keyboard layout processing for Android KCM files."""

from pathlib import Path
from typing import Optional

DEFAULT_LAYOUT = "type OVERLAY\n"
MODIFICATIONS_COMMENT = "# Custom key mappings:\n"

# Resource directory for KCM files
RESOURCES_DIR = Path(__file__).parent.parent.parent / "resources"


def get_kcm_path(name: str) -> Path:
    """Get the path to a KCM file by name."""
    return RESOURCES_DIR / "kcm" / name


def read_layout(name: str) -> Optional[str]:
    """Read a named layout from the kcm resources directory."""
    if not name:
        return None
    path = get_kcm_path(name)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def parse_map_key(line: str) -> Optional[tuple[bool, str, str]]:
    """
    Parse a 'map key' line from a KCM file.

    Returns (is_usage, code, keyCode) or None if not a valid map key line.
    """
    trimmed = line.strip()
    if not trimmed.startswith("map "):
        return None

    parts = line.split()
    if len(parts) < 4:
        return None

    if parts[1] != "key":
        return None

    if parts[2] == "usage":
        if len(parts) != 5:
            return None
        return (True, parts[3], parts[4])
    else:
        if len(parts) != 4:
            return None
        return (False, parts[2], parts[3])


def from_layout(layout: str, mappings: dict[str, str]) -> str:
    """
    Apply user mappings to a base layout.

    Args:
        layout: Base layout content
        mappings: Dict of code -> keyCode mappings to apply

    Returns:
        Modified layout content
    """
    if not mappings:
        return layout

    result = []
    remaining_mappings = dict(mappings)

    if "map " not in layout:
        # No existing mappings, just append ours
        result.append(layout)
    else:
        # Process each line, potentially commenting out conflicting mappings
        for line in layout.splitlines():
            parsed = parse_map_key(line)
            if parsed:
                is_usage, code, key_code = parsed
                full_code = f"usage {code}" if is_usage else code

                if full_code in remaining_mappings:
                    user_key_code = remaining_mappings[full_code]
                    if user_key_code == key_code:
                        # Same mapping, remove from user mappings
                        del remaining_mappings[full_code]
                    else:
                        # Different mapping, comment out the original
                        result.append(MODIFICATIONS_COMMENT)
                        result.append(f"# {line}")
                        continue

            result.append(line)
        result.append("")  # Ensure trailing newline

    # Add remaining user mappings
    if remaining_mappings:
        result.append("")
        result.append(MODIFICATIONS_COMMENT.rstrip())
        for code, key_code in remaining_mappings.items():
            result.append(f"map key {code} {key_code}")

    return "\n".join(result)


def from_named_layout(base_layout_name: Optional[str], mappings: dict[str, str]) -> str:
    """
    Create a layout from a named base layout with user mappings applied.

    Args:
        base_layout_name: Name of the base layout file (without path)
        mappings: Dict of code -> keyCode mappings to apply

    Returns:
        Complete layout content
    """
    layout = None
    if base_layout_name:
        layout = read_layout(base_layout_name)

    if layout is None:
        layout = DEFAULT_LAYOUT

    return from_layout(layout, mappings)
