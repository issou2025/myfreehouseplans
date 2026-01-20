from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class RoomBenchmarks:
    # Internal comfort ranges (not legal rules; used only for UX guidance)
    min_area_m2: float
    comfortable_area_m2: float
    # Shape helpers (still invisible to user)
    min_side_m: float = 0.0
    max_aspect_ratio: float = 0.0  # 0 means ignore


@dataclass(frozen=True)
class RoomType:
    slug: str
    label: str
    description: str
    icon: str
    benchmarks: RoomBenchmarks


ROOMS: Dict[str, RoomType] = {
    'bedroom': RoomType(
        'bedroom',
        'Bedroom',
        'A quick check for everyday comfort: does this bedroom feel easy to live in?',
        'fa-solid fa-bed',
        RoomBenchmarks(min_area_m2=9.0, comfortable_area_m2=12.0, min_side_m=2.4, max_aspect_ratio=2.6),
    ),
    'master-bedroom': RoomType(
        'master-bedroom',
        'Master bedroom',
        'Main bedroom comfort check: space to move, rest, and access storage.',
        'fa-solid fa-bed',
        RoomBenchmarks(min_area_m2=12.0, comfortable_area_m2=16.0, min_side_m=2.7, max_aspect_ratio=2.4),
    ),
    'children-room': RoomType(
        'children-room',
        "Children’s room",
        'Sleep + play + study: a small difference in size can change the feel a lot.',
        'fa-solid fa-child-reaching',
        RoomBenchmarks(min_area_m2=8.0, comfortable_area_m2=10.0, min_side_m=2.3, max_aspect_ratio=2.6),
    ),
    'living-room': RoomType(
        'living-room',
        'Living room',
        'Social comfort check: can people move around easily and relax together?',
        'fa-solid fa-couch',
        RoomBenchmarks(min_area_m2=14.0, comfortable_area_m2=20.0, min_side_m=2.8, max_aspect_ratio=2.7),
    ),
    'dining-room': RoomType(
        'dining-room',
        'Dining room',
        'Dining comfort check: does the room still feel open when people sit and stand?',
        'fa-solid fa-chair',
        RoomBenchmarks(min_area_m2=10.0, comfortable_area_m2=14.0, min_side_m=2.5, max_aspect_ratio=2.7),
    ),
    'kitchen': RoomType(
        'kitchen',
        'Kitchen',
        'Cooking comfort check: does the space feel workable day-to-day?',
        'fa-solid fa-utensils',
        RoomBenchmarks(min_area_m2=7.0, comfortable_area_m2=10.0, min_side_m=2.2, max_aspect_ratio=3.0),
    ),
    'bathroom': RoomType(
        'bathroom',
        'Bathroom',
        'Daily-use comfort check: does it feel easy to move and use the space?',
        'fa-solid fa-bath',
        RoomBenchmarks(min_area_m2=3.5, comfortable_area_m2=5.0, min_side_m=1.7, max_aspect_ratio=2.8),
    ),
    'wc': RoomType(
        'wc',
        'WC',
        'Small room, big impact: will it feel comfortable to use every day?',
        'fa-solid fa-toilet',
        RoomBenchmarks(min_area_m2=1.2, comfortable_area_m2=1.8, min_side_m=0.9, max_aspect_ratio=3.0),
    ),
    'office': RoomType(
        'office',
        'Office / Home office',
        'Work comfort check: space to sit, move your chair, and stay focused.',
        'fa-solid fa-laptop',
        RoomBenchmarks(min_area_m2=6.0, comfortable_area_m2=9.0, min_side_m=2.0, max_aspect_ratio=2.8),
    ),
    'garage': RoomType(
        'garage',
        'Garage',
        'Usability check: parking plus storage plus getting around without hassle.',
        'fa-solid fa-warehouse',
        RoomBenchmarks(min_area_m2=12.0, comfortable_area_m2=18.0, min_side_m=2.6, max_aspect_ratio=3.4),
    ),
    'corridor': RoomType(
        'corridor',
        'Corridor / Hallway',
        'Flow check: does it feel easy to walk through without bumping into things?',
        'fa-solid fa-route',
        RoomBenchmarks(min_area_m2=3.0, comfortable_area_m2=5.0, min_side_m=0.9, max_aspect_ratio=0.0),
    ),
    'entrance': RoomType(
        'entrance',
        'Entrance / Foyer',
        'First impression check: does it feel welcoming and easy to pass through?',
        'fa-solid fa-door-open',
        RoomBenchmarks(min_area_m2=3.0, comfortable_area_m2=5.0, min_side_m=1.2, max_aspect_ratio=3.0),
    ),
    'laundry': RoomType(
        'laundry',
        'Laundry room',
        'Practical check: can you use appliances without the space feeling cramped?',
        'fa-solid fa-soap',
        RoomBenchmarks(min_area_m2=3.0, comfortable_area_m2=5.0, min_side_m=1.6, max_aspect_ratio=3.2),
    ),
    'storage': RoomType(
        'storage',
        'Store / Storage room',
        'Access check: does it feel easy to use shelves and still move around?',
        'fa-solid fa-box-archive',
        RoomBenchmarks(min_area_m2=2.0, comfortable_area_m2=4.0, min_side_m=1.2, max_aspect_ratio=3.5),
    ),
    'balcony': RoomType(
        'balcony',
        'Balcony / Terrace',
        'Enjoyment check: does it feel nice to use, not just to stand in?',
        'fa-solid fa-sun',
        RoomBenchmarks(min_area_m2=3.0, comfortable_area_m2=6.0, min_side_m=1.2, max_aspect_ratio=3.5),
    ),
    'dressing': RoomType(
        'dressing',
        'Dressing room',
        'Comfort check: can you access storage and still feel relaxed moving around?',
        'fa-solid fa-shirt',
        RoomBenchmarks(min_area_m2=4.0, comfortable_area_m2=6.0, min_side_m=1.6, max_aspect_ratio=3.0),
    ),
}


ROOM_ORDER: Tuple[str, ...] = (
    'bedroom',
    'master-bedroom',
    'children-room',
    'living-room',
    'dining-room',
    'kitchen',
    'bathroom',
    'wc',
    'office',
    'garage',
    'corridor',
    'entrance',
    'laundry',
    'storage',
    'dressing',
    'balcony',
)
