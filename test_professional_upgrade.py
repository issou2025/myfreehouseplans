"""
Quick Test Script for Professional Upgrade Phase 1 & 2

This script verifies that all new fields and features are working correctly.
Run after applying migrations and updating code.
"""

from app import create_app
from app.models import HousePlan, db
from app.forms import HousePlanForm
from app.utils.unit_converter import (
    format_area_dual,
    format_dimension_dual,
    format_dimensions_box,
    format_cost_range
)

def test_database_fields():
    """Test that all new database fields exist and are accessible."""
    print("\n" + "="*60)
    print("TEST 1: Database Fields")
    print("="*60)
    
    app = create_app()
    with app.app_context():
        # Get first plan
        plan = HousePlan.query.first()
        if not plan:
            print("❌ No plans found in database")
            return False
        
        # Test new fields (should return None or value, not error)
        new_fields = [
            'public_plan_code', 'target_buyer', 'budget_category',
            'key_selling_point', 'problems_this_plan_solves', 'architectural_style',
            'living_rooms', 'kitchens', 'offices', 'terraces', 'storage_rooms',
            'min_plot_width', 'min_plot_length', 'climate_compatibility',
            'estimated_build_time', 'estimated_cost_low', 'estimated_cost_high',
            'pack1_description', 'pack2_description', 'pack3_description'
        ]
        
        print(f"\nTesting {len(new_fields)} new fields on plan: {plan.title}")
        errors = []
        
        for field_name in new_fields:
            try:
                value = getattr(plan, field_name)
                status = "✓" if value is not None else "○"
                print(f"  {status} {field_name}: {value if value is not None else '(NULL)'}")
            except AttributeError as e:
                errors.append(f"  ❌ {field_name}: Field missing!")
                print(f"  ❌ {field_name}: Field missing!")
        
        if errors:
            print(f"\n❌ {len(errors)} fields failed")
            return False
        else:
            print(f"\n✅ All {len(new_fields)} fields accessible")
            return True


def test_model_properties():
    """Test that all new model helper properties work correctly."""
    print("\n" + "="*60)
    print("TEST 2: Model Helper Properties")
    print("="*60)
    
    app = create_app()
    with app.app_context():
        plan = HousePlan.query.first()
        if not plan:
            print("❌ No plans found")
            return False
        
        properties_to_test = [
            'display_reference',
            'min_plot_area_m2',
            'min_plot_area_sqft',
            'min_plot_width_ft',
            'min_plot_length_ft',
            'building_width_ft',
            'building_length_ft',
            'total_rooms_count'
        ]
        
        print(f"\nTesting {len(properties_to_test)} helper properties:")
        errors = []
        
        for prop_name in properties_to_test:
            try:
                value = getattr(plan, prop_name)
                print(f"  ✓ {prop_name}: {value}")
            except Exception as e:
                errors.append(f"  ❌ {prop_name}: {e}")
                print(f"  ❌ {prop_name}: {e}")
        
        if errors:
            print(f"\n❌ {len(errors)} properties failed")
            return False
        else:
            print(f"\n✅ All {len(properties_to_test)} properties working")
            return True


def test_unit_converters():
    """Test unit conversion utilities and Jinja filters."""
    print("\n" + "="*60)
    print("TEST 3: Unit Conversion Utilities")
    print("="*60)
    
    # Test area conversion
    area_result = format_area_dual(120.5)
    print(f"\n  Area (120.5 m²): {area_result}")
    assert "120" in area_result and "sq ft" in area_result, "Area formatting failed"
    print(f"  ✓ format_area_dual works")
    
    # Test dimension conversion
    dim_result = format_dimension_dual(12.5)
    print(f"  Dimension (12.5 m): {dim_result}")
    assert "12.5 m" in dim_result and "ft" in dim_result, "Dimension formatting failed"
    print(f"  ✓ format_dimension_dual works")
    
    # Test box dimensions
    box_result = format_dimensions_box(10.0, 15.0)
    print(f"  Box (10m × 15m): {box_result}")
    assert "10.0 m" in box_result and "15.0 m" in box_result, "Box formatting failed"
    print(f"  ✓ format_dimensions_box works")
    
    # Test cost range
    cost_result = format_cost_range(50000, 75000)
    print(f"  Cost ($50k - $75k): {cost_result}")
    assert "$50,000" in cost_result and "$75,000" in cost_result, "Cost formatting failed"
    print(f"  ✓ format_cost_range works")
    
    print(f"\n✅ All 4 conversion functions working")
    return True


def test_form_fields():
    """Test that all new form fields exist."""
    print("\n" + "="*60)
    print("TEST 4: Form Fields")
    print("="*60)
    
    app = create_app()
    with app.app_context():
        # Create a test request context to avoid CSRF errors
        with app.test_request_context():
            form = HousePlanForm(meta={'csrf': False})
            
            new_fields = [
                'target_buyer', 'budget_category', 'architectural_style',
                'key_selling_point', 'problems_this_plan_solves',
                'living_rooms', 'kitchens', 'offices', 'terraces', 'storage_rooms',
                'min_plot_width', 'min_plot_length', 'climate_compatibility',
                'estimated_build_time', 'estimated_cost_low', 'estimated_cost_high',
                'pack1_description', 'pack2_description', 'pack3_description'
            ]
            
            print(f"\nTesting {len(new_fields)} new form fields:")
            errors = []
            
            for field_name in new_fields:
                if hasattr(form, field_name):
                    field = getattr(form, field_name)
                    print(f"  ✓ {field_name}: {type(field).__name__}")
                else:
                    errors.append(field_name)
                    print(f"  ❌ {field_name}: Missing from form")
            
            if errors:
                print(f"\n❌ {len(errors)} fields missing")
                return False
            else:
                print(f"\n✅ All {len(new_fields)} form fields exist")
                return True


def test_public_plan_codes():
    """Test that MFP-XXX codes were migrated correctly."""
    print("\n" + "="*60)
    print("TEST 5: Public Plan Codes (MFP-XXX)")
    print("="*60)
    
    app = create_app()
    with app.app_context():
        plans = HousePlan.query.all()
        
        if not plans:
            print("❌ No plans found")
            return False
        
        print(f"\nChecking {len(plans)} plans:")
        migrated = 0
        
        for plan in plans:
            if plan.public_plan_code:
                print(f"  ✓ Plan #{plan.id}: {plan.public_plan_code}")
                migrated += 1
            else:
                print(f"  ○ Plan #{plan.id}: No public code yet")
        
        if migrated > 0:
            print(f"\n✅ {migrated}/{len(plans)} plans have MFP-XXX codes")
            return True
        else:
            print(f"\n⚠️ No plans have public codes (run migration script)")
            return False


def run_all_tests():
    """Run all verification tests."""
    print("\n" + "="*60)
    print("PROFESSIONAL UPGRADE - VERIFICATION TESTS")
    print("Phase 1 & 2: Database + Backend + Admin UI")
    print("="*60)
    
    results = {
        "Database Fields": test_database_fields(),
        "Model Properties": test_model_properties(),
        "Unit Converters": test_unit_converters(),
        "Form Fields": test_form_fields(),
        "Public Plan Codes": test_public_plan_codes()
    }
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\n{'='*60}")
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        print("✅ Phase 1 & 2 implementation verified successfully!")
    else:
        print(f"⚠️ {passed}/{total} TESTS PASSED")
        print(f"❌ {total - passed} tests failed - review errors above")
    print("="*60 + "\n")
    
    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)
