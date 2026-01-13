"""Check if plan with slug '3-chambre' exists and has valid data"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.models import HousePlan

app = create_app()

with app.app_context():
    plan = HousePlan.query.filter_by(slug='3-chambre').first()
    
    if plan is None:
        print("❌ Plan with slug '3-chambre' NOT FOUND")
    else:
        print(f"✓ Plan found:")
        print(f"  ID: {plan.id}")
        print(f"  Title: {plan.title}")
        print(f"  Slug: {plan.slug}")
        print(f"  Is published: {plan.is_published}")
        print(f"  Has cover_image: {bool(plan.cover_image)}")
        print(f"  Has description: {bool(plan.description)}")
        print(f"  Has title: {bool(plan.title)}")
        print(f"  Categories count: {len(plan.categories) if plan.categories else 0}")
        
        # Check for potential issues
        issues = []
        if not plan.title:
            issues.append("Missing title")
        if not plan.description:
            issues.append("Missing description")
        if not plan.is_published:
            issues.append("Not published")
        
        if issues:
            print(f"\n⚠ ISSUES FOUND: {', '.join(issues)}")
        else:
            print("\n✓ No critical issues found")
