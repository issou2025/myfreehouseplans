"""Routes for ImmoCash Smart Floor Plan Analyzer."""

from pathlib import Path

from flask import render_template, request, session, redirect, url_for, jsonify, flash, send_file, current_app
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
                    
                    # Calculate display area based on user's unit system
                    display_area = area_m2 if unit_system == 'metric' else area_m2 * 10.7639
                    
                    room_data = {
                        'type': room_type,  # Use 'type' for template compatibility
                        'room_type': room_type,  # Keep for backward compatibility
                        'length': length_val,
                        'width': width_val,
                        'length_m': length_m,
                        'width_m': width_m,
                        'area': display_area,  # Add 'area' for template
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
    
    # Calculate total areas (internal = m²)
    total_built_area_m2 = sum(float(r.get('area_m2') or 0) for r in rooms)
    
    # Detect wasted space
    waste_analysis = detect_wasted_space(rooms)
    
    # Calculate efficiency scores
    scores = calculate_efficiency_scores(rooms, waste_analysis)
    
    # Estimate costs
    cost_analysis = estimate_construction_cost(
        total_built_area_m2,
        waste_analysis['wasted_area_m2'],
        budget,
        country
    )

    # Enrich room-level waste entries for template safety (production: never assume keys exist)
    cost_per_m2 = float(cost_analysis.get('cost_per_m2') or 0)
    area_factor = 1.0 if unit_system == 'metric' else 10.7639

    for item in waste_analysis.get('oversized_rooms', []) or []:
        waste_m2 = float(item.get('waste_m2') or item.get('waste') or 0)
        area_m2 = float(item.get('area_m2') or item.get('area') or 0)
        item['cost_waste'] = waste_m2 * cost_per_m2
        item['feedback'] = item.get('feedback', '')
        item['area'] = area_m2 * area_factor

    for item in waste_analysis.get('undersized_rooms', []) or []:
        area_m2 = float(item.get('area_m2') or item.get('area') or 0)
        item['feedback'] = item.get('feedback', '')
        item['area'] = area_m2 * area_factor
        optimal_min_m2 = float(item.get('optimal_min_m2') or 0)
        optimal_max_m2 = float(item.get('optimal_max_m2') or 0)
        item['optimal_min'] = optimal_min_m2 * area_factor
        item['optimal_max'] = optimal_max_m2 * area_factor

    # Convert summary numbers to the user's unit system for display (keep m² internally above)
    waste_view = dict(waste_analysis)
    waste_view['total_area_m2'] = float(waste_view.get('total_area_m2') or 0) * area_factor
    waste_view['wasted_area_m2'] = float(waste_view.get('wasted_area_m2') or 0) * area_factor
    waste_view['total_waste_m2'] = float(waste_view.get('total_waste_m2') or 0) * area_factor
    waste_view['circulation_area_m2'] = float(waste_view.get('circulation_area_m2') or 0) * area_factor
    
    # Build analysis object for template
    analysis = {
        'total_rooms': len(rooms),
        'total_area': total_built_area_m2 * area_factor,
        'scores': scores,
        'waste_data': waste_view,
        'cost_impact': cost_analysis
    }
    
    return render_template(
        'floor_plan/results.html',
        unit_system=unit_system,
        rooms=rooms,
        analysis=analysis,
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
    
    # Generate report (free for now)
    output_dir = Path(current_app.instance_path) / 'floor_plan_reports'
    pdf_path = generate_optimization_report(rooms, unit_system, budget, country, output_dir=output_dir)

    # For now: return a direct download so the button "just works".
    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=pdf_path.name,
        mimetype='application/pdf',
        max_age=0,
    )


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
