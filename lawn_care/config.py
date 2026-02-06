"""Configuration and state management for lawn care system."""

import json
from pathlib import Path
from typing import Any

# File paths - relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
STATE_PATH = PROJECT_ROOT / "state.json"
SCHEDULE_PATH = PROJECT_ROOT / "kc-lawn-care-plan-2026.json"


def load_json(path: Path) -> dict[str, Any]:
    """Load JSON file and return contents."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict[str, Any]) -> None:
    """Save data to JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def load_config() -> dict[str, Any]:
    """Load user configuration."""
    return load_json(CONFIG_PATH)


def load_schedule() -> dict[str, Any]:
    """Load lawn care schedule."""
    return load_json(SCHEDULE_PATH)


def load_state() -> dict[str, Any]:
    """Load application state, creating default if missing."""
    if not STATE_PATH.exists():
        return {
            "completed": {},
            "soil_temp_history": [],
            "last_soil_temp_f": None,
            "last_check": None,
        }
    return load_json(STATE_PATH)


def save_state(state: dict[str, Any]) -> None:
    """Save application state."""
    save_json(STATE_PATH, state)
