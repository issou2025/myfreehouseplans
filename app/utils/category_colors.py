"""
Category Color System for Visual Navigation

Provides consistent color coding for plan categories across the site.
Colors are soft/pastel backgrounds with strong readable text.
"""

CATEGORY_COLORS = {
    # Modern / Contemporary
    'modern': {'bg': '#eff6ff', 'border': '#bfdbfe', 'text': '#1e40af'},
    'contemporary': {'bg': '#eff6ff', 'border': '#bfdbfe', 'text': '#1e40af'},
    
    # Classic / Traditional
    'classic': {'bg': '#fef3c7', 'border': '#fde68a', 'text': '#92400e'},
    'traditional': {'bg': '#fef3c7', 'border': '#fde68a', 'text': '#92400e'},
    
    # Luxury / Premium
    'luxury': {'bg': '#d1fae5', 'border': '#a7f3d0', 'text': '#065f46'},
    'premium': {'bg': '#d1fae5', 'border': '#a7f3d0', 'text': '#065f46'},
    
    # Minimal / Simple
    'minimal': {'bg': '#f1f5f9', 'border': '#cbd5e1', 'text': '#475569'},
    'simple': {'bg': '#f1f5f9', 'border': '#cbd5e1', 'text': '#475569'},
    
    # Villa / Estate
    'villa': {'bg': '#f3e8ff', 'border': '#e9d5ff', 'text': '#6b21a8'},
    'estate': {'bg': '#f3e8ff', 'border': '#e9d5ff', 'text': '#6b21a8'},
    
    # Small / Compact
    'small': {'bg': '#fce7f3', 'border': '#fbcfe8', 'text': '#9f1239'},
    'compact': {'bg': '#fce7f3', 'border': '#fbcfe8', 'text': '#9f1239'},
    
    # Family / Residential
    'family': {'bg': '#dbeafe', 'border': '#bfdbfe', 'text': '#1e40af'},
    'residential': {'bg': '#dbeafe', 'border': '#bfdbfe', 'text': '#1e40af'},
    
    # Default fallback
    'default': {'bg': '#f8fafc', 'border': '#e2e8f0', 'text': '#475569'},
}


def get_category_color(category_name):
    """
    Get color scheme for a category.
    
    Args:
        category_name: Category name or slug
        
    Returns:
        Dict with 'bg', 'border', and 'text' hex colors
    """
    if not category_name:
        return CATEGORY_COLORS['default']
    
    key = category_name.lower().strip()
    return CATEGORY_COLORS.get(key, CATEGORY_COLORS['default'])


def get_category_style(category_name):
    """
    Get inline CSS style string for a category badge.
    
    Args:
        category_name: Category name or slug
        
    Returns:
        String with inline CSS styles
    """
    colors = get_category_color(category_name)
    return f"background: {colors['bg']}; border-color: {colors['border']}; color: {colors['text']};"
