"""
SEO Utilities Module

This module provides SEO-friendly utilities including:
- Meta tag generation
- Structured data (JSON-LD)
- Sitemap generation
- SEO-friendly URL slugs
"""

from flask import current_app, url_for
from datetime import datetime
from slugify import slugify as _slugify


def _effective_site_url() -> str:
    """Return the canonical site URL.

    Falls back to the Flask server name when SITE_URL is not configured.
    """

    configured = (current_app.config.get('SITE_URL') or '').strip()
    if configured:
        return configured.rstrip('/')
    try:
        return url_for('main.index', _external=True).rstrip('/')
    except Exception:
        return 'http://localhost:5000'


def _join_site_url(site_url: str, path_or_url: str) -> str:
    if not path_or_url:
        return site_url.rstrip('/') if site_url else ''
    if isinstance(path_or_url, str) and path_or_url.startswith(('http://', 'https://')):
        return path_or_url
    base = (site_url or '').rstrip('/')
    path = str(path_or_url)
    if not path.startswith('/'):
        path = '/' + path
    if not base:
        return path
    return base + path


def generate_meta_tags(title=None, description=None, keywords=None, image=None, url=None, type='website'):
    """
    Generate SEO meta tags for templates
    
    Args:
        title: Page title
        description: Page description
        keywords: SEO keywords (comma-separated)
        image: Open Graph image URL
        url: Canonical URL
        type: Open Graph type (website, article, product, etc.)
    
    Returns:
        dict: Dictionary of meta tags
    """
    
    # Default values from config
    site_name = current_app.config.get('SITE_NAME', 'MyFreeHousePlans')
    site_description = current_app.config.get('SITE_DESCRIPTION', '')
    site_url = (current_app.config.get('SITE_URL') or '').strip()
    if not site_url:
        site_url = _effective_site_url()
    
    # Build full title
    if title:
        full_title = f"{title} | {site_name}"
    else:
        full_title = site_name
    
    # Use defaults if not provided
    meta_description = description or site_description
    meta_keywords = keywords or current_app.config.get('SITE_KEYWORDS', '')
    canonical_url = url or site_url
    og_image = image or url_for('static', filename='images/logo.png', _external=True)
    
    return {
        'title': full_title,
        'description': meta_description,
        'keywords': meta_keywords,
        'canonical_url': canonical_url,
        'og_title': title or site_name,
        'og_description': meta_description,
        'og_image': og_image,
        'og_url': canonical_url,
        'og_type': type,
        'og_site_name': site_name,
    }


def generate_product_schema(plan):
    """
    Generate JSON-LD structured data for a house plan (product)
    
    Args:
        plan: HousePlan model instance
    
    Returns:
        dict: JSON-LD structured data
    """
    
    site_url = _effective_site_url()
    
    entry_price = plan.starting_paid_price if hasattr(plan, 'starting_paid_price') else None
    if entry_price is None and getattr(plan, 'price_pack_1', None) not in (None, 0):
        entry_price = float(plan.price_pack_1)
    if entry_price is None:
        entry_price = float(getattr(plan, 'current_price', 0) or 0)

    image_value = getattr(plan, 'cover_image', None) or getattr(plan, 'main_image', None)
    image_url = None
    try:
        if image_value:
            if isinstance(image_value, str) and image_value.startswith(('http://', 'https://')):
                image_url = image_value
            else:
                image_url = url_for('static', filename=image_value, _external=True)
    except Exception:
        image_url = None

    schema = {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": plan.title,
        "description": plan.description,
        "image": image_url,
        "sku": getattr(plan, 'reference_code', None) or f"PLAN-{plan.id}",
        "offers": {
            "@type": "Offer",
            "url": url_for('main.pack_detail', slug=plan.slug, _external=True),
            "priceCurrency": "USD",
            "price": entry_price,
            "availability": "https://schema.org/InStock",
            "seller": {
                "@type": "Organization",
                "name": current_app.config.get('SITE_NAME', 'MyFreeHousePlans')
            }
        }
    }
    
    # Add aggregate rating if available (can be implemented later)
    # schema["aggregateRating"] = {
    #     "@type": "AggregateRating",
    #     "ratingValue": "4.5",
    #     "reviewCount": "24"
    # }
    
    return schema


def generate_breadcrumb_schema(breadcrumbs):
    """
    Generate JSON-LD breadcrumb structured data
    
    Args:
        breadcrumbs: List of tuples [(name, url), ...]
    
    Returns:
        dict: JSON-LD breadcrumb list
    """
    
    site_url = _effective_site_url()
    
    items = []
    for position, (name, url) in enumerate(breadcrumbs, start=1):
        items.append({
            "@type": "ListItem",
            "position": position,
            "name": name,
            "item": _join_site_url(site_url, url)
        })
    
    return {
        "@context": "https://schema.org/",
        "@type": "BreadcrumbList",
        "itemListElement": items
    }


def generate_organization_schema():
    """
    Generate JSON-LD organization structured data
    
    Returns:
        dict: JSON-LD organization data
    """
    
    site_url = _effective_site_url()
    site_name = current_app.config.get('SITE_NAME', 'MyFreeHousePlans')

    logo_url = None
    try:
        logo_url = url_for('static', filename='images/logo.png', _external=True)
    except Exception:
        logo_url = _join_site_url(site_url, '/static/images/logo.png')
    
    return {
        "@context": "https://schema.org/",
        "@type": "Organization",
        "@id": f"{site_url}#organization",
        "name": site_name,
        "url": site_url,
        "logo": logo_url,
        "sameAs": [
            # Add social media URLs here when available
            # "https://www.facebook.com/myfreehouseplans",
            # "https://www.instagram.com/myfreehouseplans",
            # "https://www.pinterest.com/myfreehouseplans"
        ]
    }


def generate_website_schema():
    """Generate JSON-LD WebSite schema.

    Includes SearchAction pointing to the plans catalog.
    """

    site_url = _effective_site_url()
    site_name = current_app.config.get('SITE_NAME', 'MyFreeHousePlans')

    try:
        search_target = url_for('main.packs', _external=True) + '?q={search_term_string}'
    except Exception:
        search_target = _join_site_url(site_url, '/plans') + '?q={search_term_string}'

    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": f"{site_url}#website",
        "url": site_url,
        "name": site_name,
        "publisher": {"@id": f"{site_url}#organization"},
        "potentialAction": {
            "@type": "SearchAction",
            "target": search_target,
            "query-input": "required name=search_term_string",
        },
    }


def generate_sitemap(plans, categories, posts=None):
    """
    Generate XML sitemap content
    
    Args:
        plans: List of HousePlan instances
        categories: List of Category instances
    
    Returns:
        str: XML sitemap content
    """
    
    site_url = _effective_site_url()
    
    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    # Homepage
    xml_lines.append('<url>')
    xml_lines.append(f'<loc>{_join_site_url(site_url, url_for("main.index"))}</loc>')
    xml_lines.append('<changefreq>daily</changefreq>')
    xml_lines.append('<priority>1.0</priority>')
    xml_lines.append('</url>')
    
    # Plans page
    xml_lines.append('<url>')
    xml_lines.append(f'<loc>{_join_site_url(site_url, url_for("main.packs"))}</loc>')
    xml_lines.append('<changefreq>daily</changefreq>')
    xml_lines.append('<priority>0.9</priority>')
    xml_lines.append('</url>')
    
    # Individual plans
    for plan in plans:
        if plan.is_published:
            xml_lines.append('<url>')
            xml_lines.append(f'<loc>{_join_site_url(site_url, url_for("main.pack_detail", slug=plan.slug))}</loc>')
            xml_lines.append(f'<lastmod>{plan.updated_at.strftime("%Y-%m-%d")}</lastmod>')
            xml_lines.append('<changefreq>weekly</changefreq>')
            xml_lines.append('<priority>0.8</priority>')
            xml_lines.append('</url>')
    
    # Category pages
    for category in categories or []:
        try:
            xml_lines.append('<url>')
            xml_lines.append(f'<loc>{_join_site_url(site_url, url_for("main.plans_by_category", slug=category.slug))}</loc>')
            xml_lines.append('<changefreq>weekly</changefreq>')
            xml_lines.append('<priority>0.6</priority>')
            xml_lines.append('</url>')
        except Exception:
            continue

    # Blog index + posts (published)
    try:
        xml_lines.append('<url>')
        xml_lines.append(f'<loc>{_join_site_url(site_url, url_for("blog.index"))}</loc>')
        xml_lines.append('<changefreq>weekly</changefreq>')
        xml_lines.append('<priority>0.6</priority>')
        xml_lines.append('</url>')
    except Exception:
        pass

    if posts:
        for post in posts:
            try:
                xml_lines.append('<url>')
                xml_lines.append(f'<loc>{_join_site_url(site_url, url_for("blog.detail", slug=post.slug))}</loc>')
                lastmod = getattr(post, 'updated_at', None) or getattr(post, 'created_at', None)
                if lastmod:
                    xml_lines.append(f'<lastmod>{lastmod.strftime("%Y-%m-%d")}</lastmod>')
                xml_lines.append('<changefreq>monthly</changefreq>')
                xml_lines.append('<priority>0.5</priority>')
                xml_lines.append('</url>')
            except Exception:
                continue

    # Static pages (ensure endpoints actually exist)
    static_pages = [
        ('main.about', 0.6),
        ('main.contact', 0.5),
        ('main.faq', 0.5),
        ('main.privacy_policy', 0.3),
        ('main.terms_of_service', 0.3),
    ]
    
    for endpoint, priority in static_pages:
        try:
            xml_lines.append('<url>')
            xml_lines.append(f'<loc>{site_url}{url_for(endpoint)}</loc>')
            xml_lines.append('<changefreq>monthly</changefreq>')
            xml_lines.append(f'<priority>{priority}</priority>')
            xml_lines.append('</url>')
        except Exception:
            continue
    
    xml_lines.append('</urlset>')
    
    return '\n'.join(xml_lines)


def create_slug(text):
    """
    Create SEO-friendly slug from text
    
    Args:
        text: Text to slugify
    
    Returns:
        str: URL-safe slug
    """
    return _slugify(text, max_length=100)


def truncate_text(text, length=160, suffix='...'):
    """
    Truncate text for meta descriptions
    
    Args:
        text: Text to truncate
        length: Maximum length
        suffix: Suffix to add if truncated
    
    Returns:
        str: Truncated text
    """
    if len(text) <= length:
        return text
    
    return text[:length - len(suffix)].rsplit(' ', 1)[0] + suffix
