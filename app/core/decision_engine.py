from __future__ import annotations

from dataclasses import dataclass

from .elevation_logic import elevation_complexity
from .message_engine import HumanResult, human_message
from .risk_model import RiskResult, evaluate_risk, load_country_pressure
from .surface_logic import surface_risk


@dataclass(frozen=True)
class DecisionOutput:
    result: RiskResult
    human: HumanResult


def run_reality_check(*, surface_m2: int, levels_choice: str, country_name: str) -> DecisionOutput:
    surface = surface_risk(surface_m2)
    elevation = elevation_complexity(levels_choice)
    country = load_country_pressure(country_name)

    risk = evaluate_risk(surface=surface, elevation=elevation, country=country)
    human = human_message(risk)

    return DecisionOutput(result=risk, human=human)
