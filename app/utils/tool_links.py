"""Tool link registry for cross-linking articles and tools."""

from __future__ import annotations

from typing import Dict, List

from flask import url_for


ToolDefinition = Dict[str, str]


def tool_definitions() -> Dict[str, ToolDefinition]:
    return {
        "house-area-calculator": {
            "key": "house-area-calculator",
            "label": "House Area Calculator",
            "description": "Estimate full house size, room mix, and circulation with international benchmarks.",
            "href": url_for("area_calculator.index"),
        },
        "room-size": {
            "key": "room-size",
            "label": "Room Size Checker",
            "description": "Check if a room feels comfortable, tight, or not recommended.",
            "href": url_for("space_planner.room_size"),
        },
        "furniture-fit": {
            "key": "furniture-fit",
            "label": "Furniture Fit",
            "description": "Verify furniture clearances before committing to a layout.",
            "href": url_for("space_planner.furniture_fit"),
        },
    }


def get_tool_options() -> List[tuple[str, str]]:
    options = []
    for key, data in tool_definitions().items():
        options.append((key, data.get("label", key)))
    return options


def resolve_tool_link(tool_key: str) -> ToolDefinition | None:
    if not tool_key:
        return None
    return tool_definitions().get(tool_key)
