"""
Unit Conversion Utilities for International Display

Provides helper functions for converting between metric and imperial units.
All database values are stored in metric (m², meters), but templates can display both.

Usage in templates (after registering as Jinja filters):
    {{ plan.total_area_m2 | format_area_dual }}
    → "120 m² (1,291 sq ft)"
    
    {{ plan.building_width | format_dimension_dual }}
    → "12.5 m (41 ft)"
"""


def m2_to_sqft(m2_value):
    """Convert square meters to square feet.
    
    Args:
        m2_value: Area in square meters (float or numeric)
        
    Returns:
        float: Area in square feet, or None if conversion fails
    """
    try:
        return float(m2_value) * 10.7639
    except (TypeError, ValueError, AttributeError):
        return None


def sqft_to_m2(sqft_value):
    """Convert square feet to square meters.
    
    Args:
        sqft_value: Area in square feet (float or numeric)
        
    Returns:
        float: Area in square meters, or None if conversion fails
    """
    try:
        return float(sqft_value) / 10.7639
    except (TypeError, ValueError, AttributeError):
        return None


def meters_to_feet(m_value):
    """Convert meters to feet.
    
    Args:
        m_value: Length in meters (float or numeric)
        
    Returns:
        float: Length in feet, or None if conversion fails
    """
    try:
        return float(m_value) * 3.28084
    except (TypeError, ValueError, AttributeError):
        return None


def feet_to_meters(ft_value):
    """Convert feet to meters.
    
    Args:
        ft_value: Length in feet (float or numeric)
        
    Returns:
        float: Length in meters, or None if conversion fails
    """
    try:
        return float(ft_value) / 3.28084
    except (TypeError, ValueError, AttributeError):
        return None


def format_area_dual(m2_value, precision=0):
    """Format area with both metric and imperial units.
    
    Args:
        m2_value: Area in square meters (float or numeric)
        precision: Decimal places for display (default 0)
        
    Returns:
        str: Formatted string like "120 m² (1,291 sq ft)" or empty string if None
        
    Examples:
        >>> format_area_dual(120)
        "120 m² (1,291 sq ft)"
        >>> format_area_dual(85.5, precision=1)
        "85.5 m² (920.1 sq ft)"
        >>> format_area_dual(None)
        ""
    """
    if m2_value is None:
        return ""
    
    try:
        m2 = float(m2_value)
        sqft = m2_to_sqft(m2)
        
        if sqft is None:
            return f"{m2:,.{precision}f} m²"
        
        # Format with thousand separators
        if precision == 0:
            return f"{m2:,.0f} m² ({sqft:,.0f} sq ft)"
        else:
            return f"{m2:,.{precision}f} m² ({sqft:,.{precision}f} sq ft)"
            
    except (TypeError, ValueError):
        return ""


def format_dimension_dual(m_value, precision=1):
    """Format linear dimension with both metric and imperial units.
    
    Args:
        m_value: Length in meters (float or numeric)
        precision: Decimal places for display (default 1)
        
    Returns:
        str: Formatted string like "12.5 m (41 ft)" or empty string if None
        
    Examples:
        >>> format_dimension_dual(12.5)
        "12.5 m (41.0 ft)"
        >>> format_dimension_dual(8)
        "8.0 m (26.2 ft)"
        >>> format_dimension_dual(None)
        ""
    """
    if m_value is None:
        return ""
    
    try:
        meters = float(m_value)
        feet = meters_to_feet(meters)
        
        if feet is None:
            return f"{meters:.{precision}f} m"
        
        return f"{meters:.{precision}f} m ({feet:.{precision}f} ft)"
        
    except (TypeError, ValueError):
        return ""


def format_dimensions_box(width_m, length_m, precision=1):
    """Format box dimensions (width × length) with both metric and imperial.
    
    Args:
        width_m: Width in meters (float or numeric)
        length_m: Length in meters (float or numeric)
        precision: Decimal places for display (default 1)
        
    Returns:
        str: Formatted string like "12.5 m × 15.0 m (41 ft × 49 ft)" or empty if None
        
    Examples:
        >>> format_dimensions_box(12.5, 15.0)
        "12.5 m × 15.0 m (41.0 ft × 49.2 ft)"
        >>> format_dimensions_box(None, 15.0)
        ""
    """
    if width_m is None or length_m is None:
        return ""
    
    try:
        w_m = float(width_m)
        l_m = float(length_m)
        w_ft = meters_to_feet(w_m)
        l_ft = meters_to_feet(l_m)
        
        if w_ft is None or l_ft is None:
            return f"{w_m:.{precision}f} m × {l_m:.{precision}f} m"
        
        return f"{w_m:.{precision}f} m × {l_m:.{precision}f} m ({w_ft:.{precision}f} ft × {l_ft:.{precision}f} ft)"
        
    except (TypeError, ValueError):
        return ""


def format_cost_range(low, high, currency="USD"):
    """Format cost estimate range with currency.
    
    Args:
        low: Low-end cost estimate (numeric)
        high: High-end cost estimate (numeric)
        currency: Currency code (default "USD")
        
    Returns:
        str: Formatted string like "$50,000 - $75,000 USD" or empty if both None
        
    Examples:
        >>> format_cost_range(50000, 75000)
        "$50,000 - $75,000 USD"
        >>> format_cost_range(50000, None)
        "$50,000+ USD"
        >>> format_cost_range(None, None)
        ""
    """
    if low is None and high is None:
        return ""
    
    try:
        if low is not None and high is not None:
            low_val = float(low)
            high_val = float(high)
            return f"${low_val:,.0f} - ${high_val:,.0f} {currency}"
        elif low is not None:
            low_val = float(low)
            return f"${low_val:,.0f}+ {currency}"
        else:  # high is not None
            high_val = float(high)
            return f"Up to ${high_val:,.0f} {currency}"
            
    except (TypeError, ValueError):
        return ""


# Register these functions as Jinja2 filters
def register_filters(app):
    """Register all unit conversion filters with Flask app.
    
    Call this function during app initialization:
        from app.utils.unit_converter import register_filters
        register_filters(app)
    
    Then use in templates:
        {{ plan.total_area_m2 | format_area_dual }}
        {{ plan.building_width | format_dimension_dual }}
    """
    app.jinja_env.filters['m2_to_sqft'] = m2_to_sqft
    app.jinja_env.filters['sqft_to_m2'] = sqft_to_m2
    app.jinja_env.filters['meters_to_feet'] = meters_to_feet
    app.jinja_env.filters['feet_to_meters'] = feet_to_meters
    app.jinja_env.filters['format_area_dual'] = format_area_dual
    app.jinja_env.filters['format_dimension_dual'] = format_dimension_dual
    app.jinja_env.filters['format_dimensions_box'] = format_dimensions_box
    app.jinja_env.filters['format_cost_range'] = format_cost_range

    # Also register as globals so templates can call them like functions
    # (e.g., {{ format_cost_range(low, high) }}).
    try:
        app.jinja_env.globals.setdefault('m2_to_sqft', m2_to_sqft)
        app.jinja_env.globals.setdefault('sqft_to_m2', sqft_to_m2)
        app.jinja_env.globals.setdefault('meters_to_feet', meters_to_feet)
        app.jinja_env.globals.setdefault('feet_to_meters', feet_to_meters)
        app.jinja_env.globals.setdefault('format_area_dual', format_area_dual)
        app.jinja_env.globals.setdefault('format_dimension_dual', format_dimension_dual)
        app.jinja_env.globals.setdefault('format_dimensions_box', format_dimensions_box)
        app.jinja_env.globals.setdefault('format_cost_range', format_cost_range)
    except Exception:
        # Never break startup due to template helper registration issues.
        pass
