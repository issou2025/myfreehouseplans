from __future__ import annotations

from dataclasses import dataclass

from .risk_model import RiskResult


@dataclass(frozen=True)
class HumanResult:
    headline: str
    summary: str
    education: str
    advice: list[str]


def human_message(result: RiskResult) -> HumanResult:
    s = result.surface.surface_m2
    level_label = result.elevation.levels_label

    if result.zone == 'danger':
        headline = 'High risk of an unfinished project'
        summary = (
            f"A {s} m² project with {level_label.lower()} often becomes fragile near the end. "
            'The goal here is not to discourage you — it is to protect you from a stop-right-before-the-finish scenario.'
        )
        education = (
            'Most financial ruptures happen late, when stress accumulates and the last steps demand the most discipline. '
            'Bigger projects increase duration and multiply end-stage pressure.'
        )
        advice = [
            'Reduce total surface — even a moderate reduction can change the outcome.',
            'If possible, simplify levels (height adds coordination and time).',
            'Split the project into clearly finishable milestones before starting the next one.',
            'Plan for a strict buffer to protect the final stage (the end is where many projects break).',
        ]

    elif result.zone == 'tension':
        headline = 'Possible, but financially fragile'
        summary = (
            f"Your project ({s} m², {level_label.lower()}) can work, but it needs discipline. "
            'The risk is not the start — it is the finish.'
        )
        education = (
            'Projects fail less because of a single mistake and more because small overruns pile up. '
            'Your job is to protect the final stretch from becoming "optional".'
        )
        advice = [
            'Keep the project scope stable — avoid late expansions.',
            'Commit to a completion-first mindset: finish one area before starting the next.',
            'Protect a buffer for the end stage and do not touch it early.',
            'If you feel pressure, reduce surface before you increase anything else.',
        ]

    else:
        headline = 'Strong chance of completion'
        summary = (
            f"Your project ({s} m², {level_label.lower()}) is in a stable zone. "
            'That does not guarantee success — but it reduces the classic end-of-project failure risk.'
        )
        education = (
            'Even stable projects fail when scope grows over time. The safest strategy is to keep the finish protected '
            'and avoid turning a simple build into a complex one mid-way.'
        )
        advice = [
            'Keep the scope simple and stable from day one.',
            'Finish strong: protect the final phase from stress and last-minute changes.',
            'If you want upgrades, schedule them after completion, not during the build.',
        ]

    return HumanResult(headline=headline, summary=summary, education=education, advice=advice)
