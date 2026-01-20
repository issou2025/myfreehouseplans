from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .logic import FitAnalysis, OrientationResult


@dataclass(frozen=True)
class Recommendation:
    """Structured, UX-friendly result card.

    Core rule: content must depend on the room, selected item, and user-entered dimensions.
    """

    verdict: str  # Comfortable | Acceptable but tight | Not recommended
    status: str  # comfortable | tight | not_suitable

    daily_life: str
    room_recommendations: List[str]
    better_layout: str
    human_advice: str

    # Natural SEO phrases users search for (kept human and non-technical)
    seo_line: str
    # Copy users can share; also used by the UI share widget
    share_line: str


def _layout_label(r: OrientationResult) -> str:
    return 'Rotate it (90°)' if r.rotated else 'Keep it as-is'


def _comfort_phrase(verdict: str) -> str:
    if verdict == 'comfortable':
        return 'comfortable for daily use'
    if verdict == 'tight':
        return 'acceptable but tight for daily use'
    return 'not recommended for long-term use'


def _daily_life_text(analysis: FitAnalysis) -> str:
    room = analysis.room
    item = analysis.item
    v = analysis.best.verdict

    base = {
        'comfortable': f"This setup should feel { _comfort_phrase(v) } in your {room.label.lower()}.",
        'tight': f"This setup is { _comfort_phrase(v) } in your {room.label.lower()} — you’ll notice a few pinch points.",
        'not_suitable': f"This setup is { _comfort_phrase(v) } in your {room.label.lower()}.",
    }[v]

    # Room-flavored daily-life interpretation (no jargon, no numbers)
    if room.slug == 'kitchen':
        if v == 'comfortable':
            return base + f" You should be able to cook, open things, and move around without feeling boxed in around the {item.label.lower()}."
        if v == 'tight':
            return base + f" Cooking and passing by the {item.label.lower()} will work, but it may feel a bit busy when more than one person is in the kitchen."
        return base + f" In daily life, the kitchen will feel blocked around the {item.label.lower()}, especially when opening or using appliances."

    if room.slug in {'bedroom', 'master-bedroom', 'children-room'}:
        if v == 'comfortable':
            return base + f" You should be able to get in and out of the {item.label.lower()} and move around without it feeling stressful."
        if v == 'tight':
            return base + f" You’ll be able to use the {item.label.lower()}, but you may feel the tightness when walking past it or using storage."
        return base + f" Day-to-day, the bedroom will feel cramped around the {item.label.lower()} — it’s likely to become annoying over time."

    if room.slug in {'living-room'}:
        if v == 'comfortable':
            return base + f" The room should still feel open and social, with enough space to walk around the {item.label.lower()} comfortably."
        if v == 'tight':
            return base + f" It will work, but the living room may feel a bit less open when people move around the {item.label.lower()}."
        return base + f" The living room will feel crowded around the {item.label.lower()}, which can make relaxing and hosting guests less pleasant."

    if room.slug in {'bathroom', 'wc'}:
        if v == 'comfortable':
            return base + f" Using the room should feel easy, without awkward shuffling around the {item.label.lower()}."
        if v == 'tight':
            return base + f" It’s usable, but you’ll probably feel the tightness when turning or reaching past the {item.label.lower()}."
        return base + f" It will likely feel uncomfortable to use daily with the {item.label.lower()} in this space."

    if room.slug in {'office'}:
        if v == 'comfortable':
            return base + f" You should be able to sit down, move your chair, and stay focused without the {item.label.lower()} getting in your way."
        if v == 'tight':
            return base + f" It can work, but chair movement and getting in/out of your seat may feel tight around the {item.label.lower()}."
        return base + f" It’s likely to feel frustrating to work in long sessions with the {item.label.lower()} taking up this much space."

    if room.slug in {'garage'}:
        if v == 'comfortable':
            return base + f" You should be able to park and still use the space without constant squeezing around the {item.label.lower()}."
        if v == 'tight':
            return base + f" Parking may work, but getting in/out and walking around the {item.label.lower()} could feel tight."
        return base + f" In daily use, the garage will feel blocked around the {item.label.lower()}, making access and storage hard."

    # Generic fallback (still room + item specific)
    if v == 'comfortable':
        return base + f" You should be able to move around the {item.label.lower()} without it getting in the way."
    if v == 'tight':
        return base + f" It works, but movement around the {item.label.lower()} may feel tight in one area."
    return base + f" The room will feel cramped around the {item.label.lower()} in daily use."


def _room_specific_recommendations(analysis: FitAnalysis) -> List[str]:
    room = analysis.room
    item = analysis.item
    v = analysis.best.verdict

    # These must be context-aware: room + item + user-entered dimensions (verdict derived from them).
    recs: List[str] = []

    # Rotation/better-layout hint (will also be summarized separately)
    if analysis.best.rotated:
        recs.append(f"Better layout option: rotate the {item.label.lower()} to keep the room feeling more usable.")
    else:
        recs.append(f"Better layout option: keep the {item.label.lower()} as-is; it suits this room shape better.")

    if room.slug == 'kitchen':
        if item.key in {'refrigerator', 'dishwasher', 'oven', 'stove', 'sink', 'washing_machine'}:
            recs.append(f"Make sure you can comfortably stand and use the {item.label.lower()} without bumping into other things.")
            recs.append("If the result feels tight, try a slimmer model or place it so the main working area stays open.")
        elif item.key in {'kitchen_island'}:
            recs.append("An island should feel easy to walk around — if it’s tight, a smaller island (or a slim table) is usually a better option.")
            recs.append("If you cook with someone else, prioritize open movement over adding more surfaces.")
        elif item.key in {'dining_table_4', 'dining_table_6'}:
            recs.append("Make sure people can sit down and stand up without the kitchen feeling blocked.")
            recs.append("If it’s tight, a smaller table or bench seating often feels more comfortable for daily use.")
        else:
            recs.append("Keep the middle of the kitchen feeling open — it makes cooking and cleaning much nicer.")

    elif room.slug in {'bedroom', 'master-bedroom', 'children-room'}:
        if item.key.startswith('bed_'):
            recs.append("Try to keep the space around the bed easy to pass — it makes mornings and bedtime feel calmer.")
            recs.append("If it’s tight, consider a slightly narrower bed or a simpler bedside setup.")
        elif item.key in {'wardrobe', 'dresser'}:
            recs.append("Storage should feel easy to access — you don’t want to squeeze just to open and use it.")
            recs.append("If it’s tight, a less-deep wardrobe/dresser is usually the easiest comfort win.")
        elif item.key in {'desk'}:
            recs.append("For a desk, comfort is about sitting down easily and not feeling boxed in.")
            recs.append("If it’s tight, try a shallower desk or move it to a wall to free the center.")
        else:
            recs.append("Aim for a bedroom layout that feels relaxed to walk through every day.")

    elif room.slug == 'living-room':
        if item.key in {'sofa', 'sectional_sofa'}:
            recs.append("A living room should feel open for people to walk through and sit comfortably.")
            recs.append("If it’s tight, try a smaller sofa or keep extra chairs minimal.")
        elif item.key in {'coffee_table'}:
            recs.append("Coffee tables are great, but they shouldn’t make the room feel cramped when walking past.")
            recs.append("If it’s tight, a smaller table (or an ottoman) often feels better.")
        elif item.key in {'tv_unit'}:
            recs.append("Keep the TV area clean and easy to move around — it makes the room feel calmer.")
        else:
            recs.append("If you host guests, prioritize easy circulation over filling every corner.")

    elif room.slug in {'bathroom', 'wc'}:
        if item.key in {'wc'}:
            recs.append("For a WC, comfort is about being able to sit down and stand up easily.")
            recs.append("If it’s tight, consider a smaller basin or a more compact layout.")
        elif item.key in {'shower', 'bathtub'}:
            recs.append("Bathrooms should feel easy to use without awkward turning.")
            recs.append("If it’s tight, a shower often feels more practical than a large bathtub.")
        else:
            recs.append("Keep the room feeling easy to move in — it matters every single day.")

    elif room.slug == 'office':
        recs.append("Office comfort comes from chair movement and an uncluttered feel.")
        if v != 'comfortable':
            recs.append("If it’s tight, a slimmer desk or wall placement is often the best quick improvement.")

    elif room.slug == 'garage':
        if item.key == 'car':
            recs.append("Garages feel best when you can open doors and still walk around without hassle.")
            recs.append("If it’s tight, keep storage to one side so the main path stays clear.")
        else:
            recs.append("Keep the main path clear so the garage stays usable day-to-day.")

    elif room.slug in {'corridor', 'entrance'}:
        recs.append("Keep a clear walking path — it’s the difference between ‘welcoming’ and ‘annoying’.")
        if v != 'comfortable':
            recs.append("If it’s tight, try a slimmer item or move it to a spot that doesn’t interrupt passing through.")

    else:
        if v != 'comfortable':
            recs.append("If it feels tight, a smaller or less-deep option usually gives a better layout option.")
        recs.append("Try a couple of configurations — small changes can make the room feel dramatically better.")

    return recs


def _better_layout_line(analysis: FitAnalysis) -> str:
    item = analysis.item
    best = analysis.best
    other = analysis.other

    if best.rotated and best.verdict != other.verdict:
        return f"Better layout option: rotate the {item.label.lower()} (90°) — it changes the result in a good way."
    if (not best.rotated) and best.verdict != other.verdict:
        return f"Better layout option: keep the {item.label.lower()} as-is — rotating it makes the setup feel worse."
    return f"Better layout option: {_layout_label(best)}."


def _human_advice(analysis: FitAnalysis) -> str:
    room = analysis.room
    item = analysis.item
    v = analysis.best.verdict

    if v == 'comfortable':
        return f"If you like this setup, save it — it’s a solid, comfortable for daily use option. Want to double-check another {room.label.lower()} item next?"
    if v == 'tight':
        return f"You’re close. Try one small change (rotate it or choose a slightly slimmer {item.label.lower()}) and you’ll often get a better layout option."
    return f"I’d avoid this as a long-term setup. Try a smaller {item.label.lower()} or test a different placement — you’ll get a more comfortable for daily use result."


def build_recommendation(analysis: FitAnalysis) -> Recommendation:
    room = analysis.room
    item = analysis.item
    v = analysis.best.verdict

    verdict_label = {
        'comfortable': 'Comfortable',
        'tight': 'Acceptable but tight',
        'not_suitable': 'Not recommended',
    }.get(v, 'Not recommended')

    daily_life = _daily_life_text(analysis)
    room_recs = _room_specific_recommendations(analysis)
    better_layout = _better_layout_line(analysis)
    human_advice = _human_advice(analysis)

    seo_line = (
        f"Result for {room.label.lower()} + {item.label.lower()}: "
        f"{_comfort_phrase(v)} — try a better layout option if needed."
    )
    share_line = (
        f"My {room.label.lower()} setup with a {item.label.lower()} is {verdict_label.lower()} "
        f"({ _comfort_phrase(v) }). Want to test yours?"
    )

    return Recommendation(
        verdict=verdict_label,
        status=v,
        daily_life=daily_life,
        room_recommendations=room_recs,
        better_layout=better_layout,
        human_advice=human_advice,
        seo_line=seo_line,
        share_line=share_line,
    )
