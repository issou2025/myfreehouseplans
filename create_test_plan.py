"""Create a test plan to verify Phase 3 implementation"""

from app import create_app
from app.models import HousePlan, Category, db

app = create_app()

with app.app_context():
    # Check if plan already exists
    plan = HousePlan.query.first()
    
    if plan:
        print(f"✓ Plan already exists: {plan.title} ({plan.display_reference})")
    else:
        # Create test plan
        print("Creating test plan...")
        
        # Get or create category
        category = Category.query.filter_by(slug='modern').first()
        if not category:
            category = Category(name='Modern', slug='modern', description='Modern house designs')
            db.session.add(category)
            db.session.flush()
        
        plan = HousePlan(
            title='Professional Test Plan',
            slug='professional-test-plan',
            reference_code='MYFREEHOUSEPLANS-TEST/2026',
            public_plan_code='MFP-999',
            description='<p>This is a test plan to demonstrate the new professional upgrade features.</p>',
            short_description='Test plan for professional features',
            
            # Basic specs
            total_area_m2=150.0,
            number_of_bedrooms=3,
            number_of_bathrooms=2,
            number_of_floors=1,
            building_width=12.0,
            building_length=15.0,
            
            # Professional fields - Marketing
            target_buyer='Young families and first-time homebuilders',
            budget_category='Mid-range',
            architectural_style='Contemporary Modern',
            key_selling_point='Optimized for energy efficiency with large windows and open-concept living',
            problems_this_plan_solves='Maximizes natural light while maintaining privacy; efficient use of space for growing families; designed for future solar panel integration',
            
            # Professional fields - Rooms
            living_rooms=1,
            kitchens=1,
            offices=1,
            terraces=2,
            storage_rooms=1,
            
            # Professional fields - Land
            min_plot_width=15.0,
            min_plot_length=20.0,
            
            # Professional fields - Construction
            climate_compatibility='Temperate, Tropical, Subtropical',
            estimated_build_time='4-6 months',
            roof_type='Flat roof with waterproof membrane',
            structure_type='Concrete block and steel frame',
            foundation_type='Reinforced concrete slab',
            construction_complexity='Medium - suitable for most contractors',
            
            # Professional fields - Cost
            estimated_cost_low=80000.0,
            estimated_cost_high=120000.0,
            estimated_construction_cost_note='Costs vary by region, local material prices, and labor rates',
            
            # Professional fields - Packs
            pack1_description='Quick preview package perfect for initial project evaluation. Includes 3D renders, basic floor plan, and elevation views - ideal for discussing with family before committing.',
            pack2_description='Complete professional documentation set with detailed dimensions, electrical plans, and plumbing layouts. Ready for permit submission and contractor quotes. Includes all elevations and construction details.',
            pack3_description='Ultimate contractor package with editable DWG/DXF CAD files. Allows local architects to adapt plans to your specific requirements, building codes, and site conditions. Best for custom modifications.',
            
            # Other fields
            design_philosophy='<p>Open-concept design prioritizing natural light and ventilation.</p>',
            is_published=True,
            price=0.0,  # Required field
            created_by_id=1
        )
        
        db.session.add(plan)
        plan.categories.append(category)
        db.session.commit()
        
        print(f"✅ Created test plan: {plan.title} ({plan.display_reference})")
        print(f"✅ Plan ID: {plan.id}")
        print(f"✅ Slug: {plan.slug}")
        print(f"✅ URL: /plans/{plan.slug}")
        print("\n🎯 Professional Fields Populated:")
        print(f"  - Marketing: {bool(plan.key_selling_point)}")
        print(f"  - Rooms: {bool(plan.living_rooms)}")
        print(f"  - Land: {bool(plan.min_plot_width)}")
        print(f"  - Cost: {bool(plan.estimated_cost_low)}")
        print(f"  - Packs: {bool(plan.pack1_description)}")
        
    print("\n" + "="*60)
    print("TO VIEW THE UPDATED PAGE:")
    print("="*60)
    print("\n1. Start Flask: flask run")
    print(f"2. Visit: http://127.0.0.1:5000/plans/{plan.slug}")
    print(f"3. Admin: http://127.0.0.1:5000/admin/plans/edit/{plan.id}")
    print("\n✅ Phase 3 complete and ready to test!")
    print("="*60 + "\n")
