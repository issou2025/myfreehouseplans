from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class RoomSpec:
    slug: str
    label: str
    description: str
    icon: str
    item_keys: Tuple[str, ...]
    # Optional: for corridor-like spaces, we reserve a comfortable walking strip.
    preferred_walkway_cm: float = 0.0


@dataclass(frozen=True)
class ItemSpec:
    key: str
    label: str
    # Default size in centimeters (editable by user)
    default_length_cm: float
    default_width_cm: float
    # Internal movement model key (kept invisible in UX)
    movement_profile: str


# Movement profiles are interpreted in logic.py
ITEMS: Dict[str, ItemSpec] = {
    # Beds
    'bed_single': ItemSpec('bed_single', 'Single bed', 190, 90, 'bed_access'),
    'bed_double': ItemSpec('bed_double', 'Double bed', 200, 140, 'bed_access'),
    'bed_queen': ItemSpec('bed_queen', 'Queen bed', 200, 160, 'bed_access'),
    'bed_king': ItemSpec('bed_king', 'King bed', 200, 180, 'bed_access'),

    # Bedroom / storage
    'wardrobe': ItemSpec('wardrobe', 'Wardrobe', 200, 60, 'front_use_large'),
    'dresser': ItemSpec('dresser', 'Dresser', 120, 50, 'front_use_medium'),
    'bedside_table': ItemSpec('bedside_table', 'Bedside table', 50, 40, 'small_item'),
    'desk': ItemSpec('desk', 'Desk', 120, 60, 'seated_work'),

    # Living / dining
    'sofa': ItemSpec('sofa', 'Sofa', 200, 95, 'front_use_medium'),
    'sectional_sofa': ItemSpec('sectional_sofa', 'Sectional sofa', 280, 170, 'front_use_medium'),
    'armchair': ItemSpec('armchair', 'Armchair', 85, 85, 'front_use_small'),
    'coffee_table': ItemSpec('coffee_table', 'Coffee table', 110, 60, 'around_small'),
    'tv_unit': ItemSpec('tv_unit', 'TV unit', 160, 45, 'front_use_small'),
    'dining_table_4': ItemSpec('dining_table_4', 'Dining table (4 seats)', 140, 80, 'around_large'),
    'dining_table_6': ItemSpec('dining_table_6', 'Dining table (6 seats)', 180, 90, 'around_large'),

    # Kitchen appliances
    'refrigerator': ItemSpec('refrigerator', 'Refrigerator', 75, 70, 'front_use_large'),
    'stove': ItemSpec('stove', 'Stove / cooker', 60, 60, 'front_use_large'),
    'oven': ItemSpec('oven', 'Oven', 60, 60, 'front_use_large'),
    'sink': ItemSpec('sink', 'Sink base', 80, 60, 'front_use_large'),
    'dishwasher': ItemSpec('dishwasher', 'Dishwasher', 60, 60, 'front_use_large'),
    'kitchen_island': ItemSpec('kitchen_island', 'Kitchen island', 160, 90, 'around_large'),

    # Bathroom / laundry
    'shower': ItemSpec('shower', 'Shower', 90, 90, 'front_use_medium'),
    'bathtub': ItemSpec('bathtub', 'Bathtub', 170, 75, 'front_use_medium'),
    'wc': ItemSpec('wc', 'WC', 70, 40, 'front_use_medium'),
    'washbasin': ItemSpec('washbasin', 'Washbasin', 60, 50, 'front_use_medium'),
    'washing_machine': ItemSpec('washing_machine', 'Washing machine', 60, 60, 'front_use_large'),
    'storage_shelves': ItemSpec('storage_shelves', 'Storage shelves', 180, 45, 'front_use_small'),

    # Garage
    'car': ItemSpec('car', 'Car', 450, 180, 'garage_vehicle'),
    'motorcycle': ItemSpec('motorcycle', 'Motorcycle', 220, 80, 'garage_vehicle_small'),

    # Corridor / foyer
    'console_table': ItemSpec('console_table', 'Console table', 120, 35, 'wall_hug'),
    'coat_rack': ItemSpec('coat_rack', 'Coat rack', 60, 60, 'small_item'),

    # Balcony / terrace
    'outdoor_table': ItemSpec('outdoor_table', 'Outdoor table', 120, 70, 'around_small'),
    'outdoor_chairs': ItemSpec('outdoor_chairs', 'Outdoor chair', 55, 55, 'small_item'),
}


ROOMS: Dict[str, RoomSpec] = {
    'bedroom': RoomSpec('bedroom', 'Bedroom', 'Beds, wardrobes and work corners — check if it still feels easy to move around.', 'fa-solid fa-bed',
                        ('bed_single', 'bed_double', 'bed_queen', 'bed_king', 'wardrobe', 'dresser', 'bedside_table', 'desk')),
    'master-bedroom': RoomSpec('master-bedroom', 'Master bedroom', 'Main bedroom with larger furniture — keep it comfortable for daily use.', 'fa-solid fa-bed',
                               ('bed_queen', 'bed_king', 'wardrobe', 'dresser', 'bedside_table', 'desk')),
    'children-room': RoomSpec('children-room', "Children’s room", 'Sleep + play + study — avoid a cramped feel.', 'fa-solid fa-child-reaching',
                              ('bed_single', 'desk', 'wardrobe', 'dresser')),
    'living-room': RoomSpec('living-room', 'Living room', 'Sofas, seating and TV areas — check comfort for everyday movement.', 'fa-solid fa-couch',
                            ('sofa', 'sectional_sofa', 'armchair', 'coffee_table', 'tv_unit', 'dining_table_4')),
    'dining-room': RoomSpec('dining-room', 'Dining room', 'Dining tables need space to sit and stand up easily.', 'fa-solid fa-chair',
                            ('dining_table_4', 'dining_table_6', 'storage_shelves')),
    'kitchen': RoomSpec('kitchen', 'Kitchen', 'Kitchen appliances and islands — make sure the room still feels usable.', 'fa-solid fa-utensils',
                        ('refrigerator', 'stove', 'oven', 'sink', 'dishwasher', 'kitchen_island', 'dining_table_4')),
    'bathroom': RoomSpec('bathroom', 'Bathroom', 'Shower, bathtub, basin and WC — check practical day-to-day comfort.', 'fa-solid fa-bath',
                         ('shower', 'bathtub', 'washbasin', 'wc', 'washing_machine')),
    'wc': RoomSpec('wc', 'WC', 'Quick WC fit check — does it feel usable?', 'fa-solid fa-toilet',
                   ('wc', 'washbasin'), preferred_walkway_cm=0.0),
    'office': RoomSpec('office', 'Office / Home office', 'Desk and chair space — aim for a comfortable work setup.', 'fa-solid fa-laptop',
                       ('desk', 'storage_shelves')),
    'storage': RoomSpec('storage', 'Store / Storage room', 'Shelving and storage — keep access practical.', 'fa-solid fa-box-archive',
                        ('storage_shelves',)),
    'laundry': RoomSpec('laundry', 'Laundry room', 'Washing machine and storage — check if it still feels workable.', 'fa-solid fa-soap',
                        ('washing_machine', 'storage_shelves')),
    'corridor': RoomSpec('corridor', 'Corridor / Hallway', 'Keep a comfortable walking path along the corridor.', 'fa-solid fa-route',
                         ('console_table', 'coat_rack'), preferred_walkway_cm=90.0),
    'entrance': RoomSpec('entrance', 'Entrance / Foyer', 'Small furniture near the entry — keep it welcoming and easy to pass.', 'fa-solid fa-door-open',
                         ('console_table', 'coat_rack', 'storage_shelves'), preferred_walkway_cm=90.0),
    'balcony': RoomSpec('balcony', 'Balcony / Terrace', 'Outdoor furniture — keep a clear path to enjoy the space.', 'fa-solid fa-sun',
                        ('outdoor_table', 'outdoor_chairs'), preferred_walkway_cm=80.0),
    'garage': RoomSpec('garage', 'Garage', 'Vehicles and storage — make sure doors can open and you can move around.', 'fa-solid fa-warehouse',
                       ('car', 'motorcycle', 'storage_shelves'), preferred_walkway_cm=90.0),
    'dressing': RoomSpec('dressing', 'Dressing room', 'Wardrobes and storage — avoid a tight feeling when getting dressed.', 'fa-solid fa-shirt',
                         ('wardrobe', 'dresser', 'storage_shelves'), preferred_walkway_cm=90.0),
}
