"""
One-time migration script: Generate public_plan_code (MFP-XXX format)

This script extracts the numeric ID from existing reference codes like:
  - MYFREEHOUSEPLANS-013/2026
  - MYFREEHOUSEPLANS-001/2024
And converts them to clean public references:
  - MFP-013
  - MFP-001

SAFETY: Only updates rows where public_plan_code is NULL.
Does NOT delete or modify the original reference_code column.

Usage:
  python scripts/migrate_plan_codes.py
"""

import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.extensions import db
from app.models import HousePlan


PUBLIC_PLAN_CODE_PATTERN = re.compile(r'^MFP-\d{3,}$', re.IGNORECASE)


def extract_numeric_id(reference_code: str | None) -> str | None:
    """Extract numeric ID from reference like 'MYFREEHOUSEPLANS-013/2026'."""
    if not reference_code:
        return None
    
    # Pattern: MYFREEHOUSEPLANS-XXX/YYYY or similar
    match = re.search(r'(\d+)', reference_code)
    if match:
        numeric_id = match.group(1)
        # Pad to 3 digits
        return numeric_id.zfill(3)
    return None


def generate_public_code(plan: HousePlan) -> str:
    """Generate MFP-XXX code from plan reference or ID."""
    
    # Try to extract from reference_code first
    if plan.reference_code:
        extracted = extract_numeric_id(plan.reference_code)
        if extracted:
            return f"MFP-{extracted}"
    
    # Fallback: use database ID
    return f"MFP-{str(plan.id).zfill(3)}"


def is_valid_public_code(code: str | None) -> bool:
    if not code:
        return False
    return bool(PUBLIC_PLAN_CODE_PATTERN.match(code.strip()))


def migrate_plan_codes(dry_run: bool = False):
    """Migrate all plans to new public_plan_code format."""
    
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("Public Plan Code Migration (MFP-XXX Format)")
        print("=" * 60)
        print()
        
        plans_to_migrate = HousePlan.query.all()
        
        if not plans_to_migrate:
            print("✓ No plans found.")
            return
        
        print(f"Found {len(plans_to_migrate)} plans to migrate")
        print()
        
        migrated = 0
        would_migrate = 0
        errors = []
        
        for plan in plans_to_migrate:
            if is_valid_public_code(plan.public_plan_code):
                continue
            try:
                new_code = generate_public_code(plan)

                # Check for conflicts
                existing = HousePlan.query.filter_by(public_plan_code=new_code).first()
                if existing and existing.id != plan.id:
                    fallback = f"MFP-{str(plan.id).zfill(3)}"
                    fallback_existing = HousePlan.query.filter_by(public_plan_code=fallback).first()
                    if fallback_existing and fallback_existing.id != plan.id:
                        error_msg = (
                            f"Plan #{plan.id}: conflict for {new_code} and {fallback} (already used by plan #{existing.id})"
                        )
                        errors.append(error_msg)
                        print(f"  ⚠ CONFLICT: {error_msg}")
                        continue
                    new_code = fallback

                print(f"Plan #{plan.id}: '{plan.reference_code or '(no ref)'}' → '{new_code}'")

                if dry_run:
                    would_migrate += 1
                else:
                    plan.public_plan_code = new_code
                    migrated += 1
            
            except Exception as e:
                error_msg = f"Plan #{plan.id}: {str(e)}"
                errors.append(error_msg)
                print(f"  ❌ ERROR: {error_msg}")
        
        if not dry_run and migrated > 0:
            try:
                db.session.commit()
                print()
                print(f"✓ Successfully migrated {migrated} plans")
            except Exception as e:
                db.session.rollback()
                print()
                print(f"❌ Database commit failed: {e}")
                return
        
        if dry_run:
            print()
            print("=" * 60)
            print("DRY RUN: No changes were committed to the database.")
            print(f"Would migrate {would_migrate} plans.")
            print("=" * 60)
        
        if errors:
            print()
            print(f"⚠ {len(errors)} errors encountered:")
            for err in errors:
                print(f"  - {err}")
        
        print()
        print("Migration complete.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate plan reference codes to MFP-XXX format")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without committing")
    args = parser.parse_args()
    
    migrate_plan_codes(dry_run=args.dry_run)
