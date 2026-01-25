"""Routes for ImmoCash Smart Floor Plan Analyzer."""

from flask import render_template, request, session, redirect, url_for, jsonify, flash
from . import floor_plan_bp
from .services import (
    validate_room_dimensions,
    calculate_efficiency_scores,
    detect_wasted_space,
    get_room_type_options,
    convert_to_metric,
    format_dimension_for_display,
    estimate_construction_cost,
    generate_optimization_report
)


@floor_plan_bp.route('/')
def landing():
    """SEO-optimized landing page."""
    meta = {
        'title': 'Smart Floor Plan Cost Optimizer & Waste Detector | Free Analysis',
        'description': 'Analyze house floor plans, detect wasted space, reduce construction costs, and optimize room dimensions using international building standards — even without a budget.',
        'keywords': 'floor plan analyzer, construction cost calculator, wasted space detector, room dimension optimizer, house plan efficiency, residential cost savings',
        'og_type': 'website',
        'og_title': 'Is Your House Floor Plan Quietly Costing You Thousands?',
        'og_description': 'Free floor plan analysis tool. Detect wasted space and optimize costs using international standards.',
    }
    return render_template('floor_plan/landing.html', meta=meta)


@floor_plan_bp.route('/start', methods=['GET', 'POST'])
def start():
    """Step 0: Unit system selection."""
    if request.method == 'POST':
        unit_system = request.form.get('unit_system', 'metric')
        session['fp_unit_system'] = unit_system
        return redirect(url_for('floor_plan.budget_input'))
    
    return render_template('floor_plan/unit_selection.html')


@floor_plan_bp.route('/budget', methods=['GET', 'POST'])
def budget_input():
    """Step 1: Budget input (optional)."""
    if 'fp_unit_system' not in session:
        return redirect(url_for('floor_plan.start'))
    
    if request.method == 'POST':
        # Budget is optional - store if provided
        budget = request.form.get('budget', '').strip()
        mortgage_duration = request.form.get('mortgage_duration', '').strip()
        country = request.form.get('country', 'International').strip()
        
        session['fp_budget'] = float(budget) if budget else None
        session['fp_mortgage_duration'] = int(mortgage_duration) if mortgage_duration else None
        session['fp_country'] = country
        session['fp_rooms'] = []
        
        return redirect(url_for('floor_plan.room_input'))
    
    unit_system = session.get('fp_unit_system', 'metric')
    return render_template('floor_plan/budget_input.html', unit_system=unit_system)


@floor_plan_bp.route('/rooms', methods=['GET', 'POST'])
def room_input():
    """Step 2: Room-by-room input."""
    if 'fp_unit_system' not in session:
        return redirect(url_for('floor_plan.start'))
    
    unit_system = session.get('fp_unit_system', 'metric')
    rooms = session.get('fp_rooms', [])
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_room':
            room_type = request.form.get('room_type')
            length = request.form.get('length')
            width = request.form.get('width')
            
            if room_type and length and width:
                try:
                    length_val = float(length)
                    width_val = float(width)
                    
                    # Convert to metric for internal storage
                    length_m, width_m = convert_to_metric(length_val, width_val, unit_system)
                    area_m2 = length_m * width_m
                    
                    # Validate against standards
                    validation = validate_room_dimensions(room_type, length_m, width_m, area_m2)
                    
                    room_data = {
                        'room_type': room_type,
                        'length': length_val,
                        'width': width_val,
                        'length_m': length_m,
                        'width_m': width_m,
                        'area_m2': area_m2,
                        'validation': validation
                    }
                    
                    rooms.append(room_data)
                    session['fp_rooms'] = rooms
                    flash(f'{room_type} added successfully!', 'success')
                    
                except ValueError:
                    flash('Please enter valid numbers for dimensions.', 'error')
        
        elif action == 'remove_room':
            room_index = int(request.form.get('room_index', -1))
            if 0 <= room_index < len(rooms):
                removed = rooms.pop(room_index)
                session['fp_rooms'] = rooms
                flash(f'{removed["room_type"]} removed.', 'info')
        
        elif action == 'analyze':
            if len(rooms) >= 3:
                return redirect(url_for('floor_plan.results'))
            else:
                flash('Please add at least 3 rooms for accurate analysis.', 'warning')
    
    room_options = get_room_type_options()
    
    return render_template(
        'floor_plan/room_input.html',
        unit_system=unit_system,
        rooms=rooms,
        room_options=room_options
    )


@floor_plan_bp.route('/results')
def results():
    """Final dashboard with efficiency scores."""
    if 'fp_unit_system' not in session or 'fp_rooms' not in session:
        return redirect(url_for('floor_plan.start'))
    
    rooms = session.get('fp_rooms', [])
    if len(rooms) < 3:
        flash('Please add at least 3 rooms for analysis.', 'warning')
        return redirect(url_for('floor_plan.room_input'))
    
    unit_system = session.get('fp_unit_system', 'metric')
    budget = session.get('fp_budget')
    country = session.get('fp_country', 'International')
    
    # Calculate total areas
    total_built_area = sum(r['area_m2'] for r in rooms)
    
    # Detect wasted space
    waste_analysis = detect_wasted_space(rooms)
    
    # Calculate efficiency scores
    scores = calculate_efficiency_scores(rooms, waste_analysis)
    
    # Estimate costs
    cost_analysis = estimate_construction_cost(
        total_built_area,
        waste_analysis['wasted_area_m2'],
        budget,
        country
    )
    
    return render_template(
        'floor_plan/results.html',
        unit_system=unit_system,
        rooms=rooms,
        total_built_area=total_built_area,
        waste_analysis=waste_analysis,
        scores=scores,
        cost_analysis=cost_analysis,
        budget=budget
    )


@floor_plan_bp.route('/report/generate', methods=['POST'])
def generate_report():
    """Generate premium PDF optimization report."""
    if 'fp_rooms' not in session:
        return jsonify({'error': 'No analysis data found'}), 400
    
    rooms = session.get('fp_rooms', [])
    unit_system = session.get('fp_unit_system', 'metric')
    budget = session.get('fp_budget')
    country = session.get('fp_country', 'International')
    
    # Generate report
    pdf_path = generate_optimization_report(rooms, unit_system, budget, country)
    
    # In production, this would handle payment/authentication
    # For now, return success
    return jsonify({
        'success': True,
        'message': 'Report generated successfully',
        'download_url': url_for('floor_plan.download_report', filename=pdf_path.name)
    })


@floor_plan_bp.route('/reset')
def reset():
    """Clear session and restart analysis."""
    session.pop('fp_unit_system', None)
    session.pop('fp_budget', None)
    session.pop('fp_mortgage_duration', None)
    session.pop('fp_country', None)
    session.pop('fp_rooms', None)
    flash('Analysis reset. Start a new analysis!', 'info')
    return redirect(url_for('floor_plan.landing'))
