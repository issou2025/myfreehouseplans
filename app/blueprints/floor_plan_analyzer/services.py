"""Service layer for floor plan analysis - International Standards & Validation Engine."""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class RoomStandard:
    """International dimensional standards for a room type."""
    min_area_m2: float
    optimal_min_m2: float
    optimal_max_m2: float
    oversized_threshold_m2: float
    min_width_m: float
    optimal_width_range: Tuple[float, float]
    efficiency_notes: Dict[str, str]


# INTERNATIONAL ROOM STANDARDS DATABASE
ROOM_STANDARDS = {
    'Bedroom': RoomStandard(
        min_area_m2=9.0,
        optimal_min_m2=12.0,
        optimal_max_m2=16.0,
        oversized_threshold_m2=18.0,
        min_width_m=2.7,
        optimal_width_range=(3.0, 3.6),
        efficiency_notes={
            'undersized': 'This bedroom is below international comfort standards. Furniture placement will be difficult.',
            'optimal': 'This bedroom meets international standards for comfortable living.',
            'oversized': 'This bedroom exceeds functional needs. Extra space increases costs without added comfort.'
        }
    ),
    'Master Bedroom': RoomStandard(
        min_area_m2=12.0,
        optimal_min_m2=14.0,
        optimal_max_m2=20.0,
        oversized_threshold_m2=24.0,
        min_width_m=3.0,
        optimal_width_range=(3.3, 4.2),
        efficiency_notes={
            'undersized': 'This master bedroom is smaller than recommended for a primary suite.',
            'optimal': 'This master bedroom provides excellent comfort and functionality.',
            'oversized': 'This master bedroom is larger than necessary. Consider reallocating space to other areas.'
        }
    ),
    "Children's Bedroom": RoomStandard(
        min_area_m2=9.0,
        optimal_min_m2=10.0,
        optimal_max_m2=14.0,
        oversized_threshold_m2=16.0,
        min_width_m=2.7,
        optimal_width_range=(2.8, 3.3),
        efficiency_notes={
            'undersized': "This children's bedroom is too small for comfortable use and growth.",
            'optimal': "This children's bedroom is well-sized for long-term use.",
            'oversized': "This children's bedroom is larger than necessary, increasing construction costs."
        }
    ),
    'Living Room': RoomStandard(
        min_area_m2=16.0,
        optimal_min_m2=20.0,
        optimal_max_m2=30.0,
        oversized_threshold_m2=35.0,
        min_width_m=3.5,
        optimal_width_range=(4.0, 5.5),
        efficiency_notes={
            'undersized': 'This living room may feel cramped for family gatherings.',
            'optimal': 'This living room provides comfortable space for daily living and entertaining.',
            'oversized': 'This living room is oversized. Large rooms require more heating, cooling, and furnishing.'
        }
    ),
    'Dining Room': RoomStandard(
        min_area_m2=10.0,
        optimal_min_m2=12.0,
        optimal_max_m2=18.0,
        oversized_threshold_m2=22.0,
        min_width_m=2.8,
        optimal_width_range=(3.0, 4.0),
        efficiency_notes={
            'undersized': 'This dining room is too small for comfortable family meals.',
            'optimal': 'This dining room is appropriately sized for daily use.',
            'oversized': 'This dining room is larger than necessary for typical household needs.'
        }
    ),
    'Closed Kitchen': RoomStandard(
        min_area_m2=8.0,
        optimal_min_m2=10.0,
        optimal_max_m2=14.0,
        oversized_threshold_m2=16.0,
        min_width_m=2.4,
        optimal_width_range=(2.6, 3.2),
        efficiency_notes={
            'undersized': 'This kitchen lacks adequate counter and storage space.',
            'optimal': 'This kitchen provides efficient workspace and storage.',
            'oversized': 'This kitchen is oversized, creating inefficient movement patterns and wasted walking distance.'
        }
    ),
    'Open Kitchen': RoomStandard(
        min_area_m2=12.0,
        optimal_min_m2=14.0,
        optimal_max_m2=20.0,
        oversized_threshold_m2=24.0,
        min_width_m=3.0,
        optimal_width_range=(3.5, 4.5),
        efficiency_notes={
            'undersized': 'This open kitchen lacks adequate space for both cooking and living functions.',
            'optimal': 'This open kitchen balances cooking workspace with social interaction.',
            'oversized': 'This open kitchen is excessive. Large kitchens increase walking distances and reduce efficiency.'
        }
    ),
    'Bathroom': RoomStandard(
        min_area_m2=3.5,
        optimal_min_m2=4.5,
        optimal_max_m2=7.0,
        oversized_threshold_m2=9.0,
        min_width_m=1.8,
        optimal_width_range=(2.0, 2.5),
        efficiency_notes={
            'undersized': 'This bathroom is below minimum functional standards.',
            'optimal': 'This bathroom provides comfortable functionality.',
            'oversized': 'This bathroom is larger than necessary. Bathrooms should be efficient, not spacious.'
        }
    ),
    'Corridor': RoomStandard(
        min_area_m2=0.0,  # No minimum - depends on length
        optimal_min_m2=0.0,
        optimal_max_m2=0.0,
        oversized_threshold_m2=0.0,
        min_width_m=0.9,
        optimal_width_range=(1.0, 1.2),
        efficiency_notes={
            'undersized': 'This corridor is too narrow for comfortable passage.',
            'optimal': 'This corridor width is appropriate for efficient circulation.',
            'oversized': 'This corridor is wider than necessary. Every extra 10cm multiplies wasted area across the entire length.'
        }
    ),
    'Hallway': RoomStandard(
        min_area_m2=0.0,
        optimal_min_m2=0.0,
        optimal_max_m2=0.0,
        oversized_threshold_m2=0.0,
        min_width_m=1.0,
        optimal_width_range=(1.2, 1.5),
        efficiency_notes={
            'undersized': 'This hallway is too narrow.',
            'optimal': 'This hallway width is efficient.',
            'oversized': 'This hallway is wider than necessary, creating significant wasted area.'
        }
    ),
    'Garage': RoomStandard(
        min_area_m2=15.0,
        optimal_min_m2=18.0,
        optimal_max_m2=24.0,
        oversized_threshold_m2=30.0,
        min_width_m=3.0,
        optimal_width_range=(3.5, 5.5),
        efficiency_notes={
            'undersized': 'This garage is too small for a standard vehicle plus storage.',
            'optimal': 'This garage is appropriately sized.',
            'oversized': 'This garage is oversized. Consider whether the extra space justifies the cost.'
        }
    ),
    'Storage': RoomStandard(
        min_area_m2=2.0,
        optimal_min_m2=3.0,
        optimal_max_m2=6.0,
        oversized_threshold_m2=8.0,
        min_width_m=1.2,
        optimal_width_range=(1.5, 2.0),
        efficiency_notes={
            'undersized': 'This storage space is insufficient.',
            'optimal': 'This storage space is well-sized.',
            'oversized': 'This storage space is excessive. Smaller, well-organized storage is more efficient.'
        }
    ),
}

# Default standard for unmapped room types
DEFAULT_STANDARD = RoomStandard(
    min_area_m2=6.0,
    optimal_min_m2=8.0,
    optimal_max_m2=15.0,
    oversized_threshold_m2=20.0,
    min_width_m=2.0,
    optimal_width_range=(2.5, 4.0),
    efficiency_notes={
        'undersized': 'This space is smaller than typical functional requirements.',
        'optimal': 'This space appears appropriately sized.',
        'oversized': 'This space is larger than necessary for its function.'
    }
)


def get_room_type_options() -> List[Dict[str, str]]:
    """Return all room type options for the spinner/dropdown."""
    categories = {
        'Living Areas': [
            'Living Room',
            'Family Room',
            'Dining Room',
            'Living + Dining (Open Plan)'
        ],
        'Bedrooms': [
            'Bedroom',
            'Master Bedroom',
            "Children's Bedroom",
            'Guest Bedroom',
            'Dormitory'
        ],
        'Kitchen Areas': [
            'Closed Kitchen',
            'Open Kitchen',
            'Kitchen + Dining',
            'Kitchenette'
        ],
        'Bathrooms': [
            'Bathroom',
            'Shower Room',
            'WC',
            'Guest WC'
        ],
        'Circulation Areas': [
            'Corridor',
            'Hallway',
            'Entrance',
            'Lobby'
        ],
        'Technical / Utility': [
            'Storage',
            'Pantry',
            'Laundry Room',
            'Utility Room',
            'Mechanical Room'
        ],
        'Special Use': [
            'Office',
            'Prayer Room',
            'Multipurpose Room',
            'Library'
        ],
        'Annexes': [
            'Garage',
            'Carport',
            'Workshop',
            'Shop / Commercial Space'
        ],
        'Covered Outdoor': [
            'Covered Terrace',
            'Veranda',
            'Balcony'
        ],
        'Other': [
            'Other Space'
        ]
    }
    
    return categories


def convert_to_metric(length: float, width: float, unit_system: str) -> Tuple[float, float]:
    """Convert dimensions to metric (meters)."""
    if unit_system == 'imperial':
        # Convert feet to meters
        length_m = length * 0.3048
        width_m = width * 0.3048
    else:
        length_m = length
        width_m = width
    
    return length_m, width_m


def format_dimension_for_display(value_m: float, unit_system: str) -> str:
    """Format metric dimension for display in user's unit system."""
    if unit_system == 'imperial':
        value_ft = value_m / 0.3048
        return f"{value_ft:.1f} ft"
    else:
        return f"{value_m:.2f} m"


def validate_room_dimensions(room_type: str, length_m: float, width_m: float, area_m2: float) -> Dict:
    """
    Validate room dimensions against international standards.
    Returns status (green/orange/red) and feedback message.
    """
    standard = ROOM_STANDARDS.get(room_type, DEFAULT_STANDARD)
    
    # Check width
    width_status = 'optimal'
    width_feedback = ''
    
    if width_m < standard.min_width_m:
        width_status = 'critical'
        width_feedback = f'Width is below minimum standard ({standard.min_width_m:.1f}m).'
    elif width_m < standard.optimal_width_range[0]:
        width_status = 'warning'
        width_feedback = f'Width is narrower than optimal range ({standard.optimal_width_range[0]:.1f}-{standard.optimal_width_range[1]:.1f}m).'
    elif width_m > standard.optimal_width_range[1] * 1.3:
        width_status = 'warning'
        width_feedback = f'Width is excessive. Every extra meter adds cost without benefit.'
    
    # Check area
    area_status = 'optimal'
    area_feedback = ''
    waste_level = 0.0
    
    if area_m2 < standard.min_area_m2:
        area_status = 'critical'
        area_feedback = standard.efficiency_notes['undersized']
    elif area_m2 < standard.optimal_min_m2:
        area_status = 'warning'
        area_feedback = 'This space is slightly below recommended standards.'
    elif area_m2 <= standard.optimal_max_m2:
        area_status = 'optimal'
        area_feedback = standard.efficiency_notes['optimal']
    elif area_m2 <= standard.oversized_threshold_m2:
        area_status = 'warning'
        area_feedback = standard.efficiency_notes['oversized']
        waste_level = (area_m2 - standard.optimal_max_m2) / area_m2
    else:
        area_status = 'critical'
        area_feedback = standard.efficiency_notes['oversized']
        waste_level = (area_m2 - standard.optimal_max_m2) / area_m2
    
    # Overall status
    if area_status == 'critical' or width_status == 'critical':
        overall_status = 'red'
        status_icon = '🔴'
    elif area_status == 'warning' or width_status == 'warning':
        overall_status = 'orange'
        status_icon = '🟠'
    else:
        overall_status = 'green'
        status_icon = '🟢'
    
    return {
        'status': overall_status,
        'status_icon': status_icon,
        'area_status': area_status,
        'width_status': width_status,
        'feedback': area_feedback,
        'width_feedback': width_feedback,
        'waste_level': waste_level,
        'optimal_range': f"{standard.optimal_min_m2:.0f}-{standard.optimal_max_m2:.0f} m²"
    }


def detect_wasted_space(rooms: List[Dict]) -> Dict:
    """
    Analyze all rooms to detect total wasted space.
    Returns comprehensive waste analysis.
    """
    total_area = sum(r.get('area_m2', 0) for r in rooms)
    total_waste = 0.0
    circulation_area = 0.0
    oversized_rooms = []
    undersized_rooms = []
    
    for room in rooms:
        validation = room.get('validation', {})
        area = room.get('area_m2', 0)
        room_type = room.get('room_type', room.get('type', 'Unknown'))
        
        # Track circulation spaces
        if room_type in ['Corridor', 'Hallway', 'Entrance', 'Lobby']:
            circulation_area += area
        
        # Calculate waste from oversized rooms
        waste_level = validation.get('waste_level', 0)
        if waste_level > 0:
            waste = area * waste_level
            total_waste += waste
            oversized_rooms.append({
                'type': room_type,
                'area': area,
                'waste': waste
            })
        
        # Track undersized rooms
        area_status = validation.get('area_status', 'optimal')
        if area_status == 'critical' and waste_level == 0:
            undersized_rooms.append({
                'type': room_type,
                'area': area
            })
    
    # Calculate circulation percentage
    circulation_pct = (circulation_area / total_area * 100) if total_area > 0 else 0
    
    # Circulation warning if > 15%
    circulation_warning = circulation_pct > 15
    
    # Calculate wasted percentage
    waste_pct = (total_waste / total_area * 100) if total_area > 0 else 0
    
    return {
        'total_area_m2': total_area,
        'wasted_area_m2': total_waste,
        'total_waste_m2': total_waste,  # Add alternate key for template compatibility
        'waste_percentage': waste_pct,
        'circulation_area_m2': circulation_area,
        'circulation_percentage': circulation_pct,
        'circulation_warning': circulation_warning,
        'oversized_rooms': oversized_rooms,
        'undersized_rooms': undersized_rooms,
        'has_issues': len(oversized_rooms) > 0 or len(undersized_rooms) > 0 or circulation_warning
    }


def calculate_efficiency_scores(rooms: List[Dict], waste_analysis: Dict) -> Dict:
    """
    Calculate three efficiency scores (0-100):
    1. Financial Efficiency
    2. Daily Comfort
    3. Circulation & Flow
    """
    # Financial Efficiency (inverse of waste)
    waste_pct = waste_analysis['waste_percentage']
    financial_score = max(0, 100 - (waste_pct * 2))  # Heavy penalty for waste
    
    # Daily Comfort (based on room sizing)
    optimal_count = sum(1 for r in rooms if r.get('validation', {}).get('status') == 'green')
    warning_count = sum(1 for r in rooms if r.get('validation', {}).get('status') == 'orange')
    critical_count = sum(1 for r in rooms if r.get('validation', {}).get('status') == 'red')
    
    total_rooms = len(rooms)
    comfort_score = (optimal_count * 100 + warning_count * 60 + critical_count * 20) / total_rooms if total_rooms > 0 else 50
    
    # Circulation & Flow
    circulation_pct = waste_analysis['circulation_percentage']
    if circulation_pct < 10:
        circulation_score = 90
    elif circulation_pct < 15:
        circulation_score = 75
    elif circulation_pct < 20:
        circulation_score = 50
    else:
        circulation_score = 30
    
    # Adjust for excessive corridors
    corridor_penalty = min(30, circulation_pct - 10) if circulation_pct > 10 else 0
    circulation_score = max(0, circulation_score - corridor_penalty)
    
    return {
        'financial_efficiency': int(financial_score),
        'comfort_efficiency': int(comfort_score),
        'circulation_efficiency': int(circulation_score),
        'overall': int((financial_score + comfort_score + circulation_score) / 3)
    }


def estimate_construction_cost(
    total_area_m2: float,
    wasted_area_m2: float,
    user_budget: Optional[float],
    country: str
) -> Dict:
    """
    Estimate construction costs and financial impact of waste.
    Works with or without user budget.
    """
    # International average construction costs per m² (USD)
    REGIONAL_COSTS = {
        'United States': 2200,
        'Canada': 2000,
        'United Kingdom': 2400,
        'Australia': 2300,
        'Germany': 2100,
        'France': 2000,
        'Spain': 1500,
        'Italy': 1600,
        'International': 1800,
    }
    
    standard_cost_per_m2 = REGIONAL_COSTS.get(country, 1800)
    
    if user_budget:
        # User provided budget - calculate actual cost per m²
        cost_per_m2 = user_budget / total_area_m2 if total_area_m2 > 0 else standard_cost_per_m2
        mode = 'user_budget'
    else:
        # No budget - use international standard
        cost_per_m2 = standard_cost_per_m2
        mode = 'standard'
    
    # Calculate waste cost
    wasted_money = wasted_area_m2 * cost_per_m2
    
    # Calculate optimized costs
    optimized_area = total_area_m2 - wasted_area_m2
    optimized_total_cost = optimized_area * cost_per_m2
    current_total_cost = total_area_m2 * cost_per_m2
    potential_savings = wasted_money
    
    return {
        'mode': mode,
        'cost_per_m2': cost_per_m2,
        'standard_cost_per_m2': standard_cost_per_m2,
        'total_area_m2': total_area_m2,
        'wasted_area_m2': wasted_area_m2,
        'wasted_money': wasted_money,
        'wasted_budget': wasted_money,  # Add alternate key for template compatibility
        'current_total_cost': current_total_cost,
        'optimized_total_cost': optimized_total_cost,
        'potential_savings': potential_savings,
        'savings_percentage': (potential_savings / current_total_cost * 100) if current_total_cost > 0 else 0
    }


def generate_optimization_report(
    rooms: List[Dict],
    unit_system: str,
    budget: Optional[float],
    country: str
) -> str:
    """
    Generate premium PDF optimization report.
    (Stub - full implementation would use ReportLab)
    """
    # This would generate a comprehensive PDF report
    # For now, return a placeholder
    return 'floor_plan_analysis_report.pdf'
