"""
ScenarioLoader — reads scenario JSON files from the scenarios/ directory.

Scenarios are loaded once on first access and cached in memory.
Adding a new scenario only requires dropping a JSON file into scenarios/;
no code changes are needed.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# scenarios/ is at the project root — two levels up from backend/core/
_SCENARIOS_DIR = Path(__file__).resolve().parent.parent.parent / "scenarios"

_cache: Dict[str, Dict[str, Any]] = {}


def _ensure_loaded() -> Dict[str, Dict[str, Any]]:
    global _cache
    if _cache:
        return _cache

    result: Dict[str, Dict[str, Any]] = {}
    if not _SCENARIOS_DIR.exists():
        logger.error("Scenarios directory not found: %s", _SCENARIOS_DIR)
        return result

    for path in sorted(_SCENARIOS_DIR.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
            scenario_id: str = data.get("id", path.stem)
            result[scenario_id] = data
            logger.info("Loaded scenario: %s (%s)", scenario_id, data.get("display_name"))
        except Exception as exc:
            logger.error("Failed to load %s: %s", path.name, exc)

    _cache = result
    logger.info("Scenario library ready: %d scenarios.", len(result))
    return result


def get_all_scenarios() -> Dict[str, Dict[str, Any]]:
    """Return all loaded scenarios keyed by scenario_id."""
    return _ensure_loaded()


def get_scenario(scenario_id: str) -> Optional[Dict[str, Any]]:
    """Return a single scenario by ID, or None if not found."""
    return _ensure_loaded().get(scenario_id)


def list_scenarios_safe() -> List[Dict[str, Any]]:
    """Return user-safe scenario summaries (no hidden fields)."""
    return [
        {
            "id": s.get("id"),
            "display_name": s.get("display_name"),
            "user_role": s.get("user_role"),
            "opponent_role": s.get("opponent_role"),
            "icon": s.get("icon", "🤝"),
            "description": s.get("description", ""),
            "max_turns": s.get("max_turns", 10),
            "value_unit": s.get("value_unit", ""),
        }
        for s in _ensure_loaded().values()
    ]
