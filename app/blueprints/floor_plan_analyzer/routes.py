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
    try:
        if request.method == 'POST':
            unit_system = request.form.get('unit_system', 'metric')
            if unit_system not in ['metric', 'imperial']:
                unit_system = 'metric'
            session['fp_unit_system'] = unit_system
            return redirect(url_for('floor_plan.budget_input'))
        
        return render_template('floor_plan/unit_selection.html')
    except Exception as exc:
        current_app.logger.exception('Unit selection failed: %s', exc)
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('floor_plan.landing'))


@floor_plan_bp.route('/budget', methods=['GET', 'POST'])
def budget_input():
    """Step 1: Budget input (optional)."""
    try:
        if 'fp_unit_system' not in session:
            return redirect(url_for('floor_plan.start'))
        
        if request.method == 'POST':
            # Budget is optional - store if provided
            budget = request.form.get('budget', '').strip()
            mortgage_duration = request.form.get('mortgage_duration', '').strip()
            country = request.form.get('country', 'International').strip()
            
            session['fp_budget'] = float(budget) if budget else None
            session['fp_mortgage_duration'] = int(mortgage_duration) if mortgage_duration else None
            session['fp_country'] = country if country else 'International'
            session['fp_rooms'] = []
            
            return redirect(url_for('floor_plan.room_input'))
        
        unit_system = session.get('fp_unit_system', 'metric')
        return render_template('floor_plan/budget_input.html', unit_system=unit_system)
    except Exception as exc:
        current_app.logger.exception('Budget input failed: %s', exc)
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('floor_plan.start'))


@floor_plan_bp.route('/rooms', methods=['GET', 'POST'])
def room_input():
    """Step 2: Room-by-room input."""
    try:
        if 'fp_unit_system' not in session:
            return redirect(url_for('floor_plan.start'))
        
        unit_system = session.get('fp_unit_system', 'metric')
        rooms = session.get('fp_rooms', [])
        
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'add_room':
                room_type = request.form.get('room_type')
                input_method = request.form.get('input_method', 'dimensions')
                
                # Get inputs based on method
                length = request.form.get('length', '').strip()
                width = request.form.get('width', '').strip()
                surface = request.form.get('surface', '').strip()
                
                if not room_type:
                    flash('Please select a room type.', 'error')
                elif input_method == 'surface' and surface:
                    # Direct surface input
                    try:
                        surface_val = float(surface)
                        
                        if surface_val <= 0:
                            flash('Surface area must be greater than zero.', 'error')
                        else:
                            # Convert surface to metric if needed
                            area_m2 = surface_val if unit_system == 'metric' else surface_val / 10.7639
                            
                            # For surface input, we don't have specific dimensions
                            # Use sqrt to estimate dimensions for validation
                            import math
                            estimated_side = math.sqrt(area_m2)
                            
                            # Validate against standards using estimated dimensions
                            validation = validate_room_dimensions(room_type, estimated_side, estimated_side, area_m2)
                            
                            # Calculate display area
                            display_area = area_m2 if unit_system == 'metric' else area_m2 * 10.7639
                            
                            room_data = {
                                'type': room_type,
                                'room_type': room_type,
                                'length': None,  # No specific dimensions
                                'width': None,
                                'length_m': None,
                                'width_m': None,
                                'area': display_area,
                                'area_m2': area_m2,
                                'input_method': 'surface',
                                'validation': validation
                            }
                            
                            rooms.append(room_data)
                            session['fp_rooms'] = rooms
                            flash(f'{room_type} added successfully!', 'success')
                        
                    except (ValueError, TypeError) as e:
                        flash('Please enter a valid surface area.', 'error')
                    except Exception as e:
                        current_app.logger.exception('Error adding room with surface: %s', e)
                        flash('An error occurred. Please try again.', 'error')
                        
                elif input_method == 'dimensions' and length and width:
                    # Existing dimension-based logic (unchanged)
                    try:
                        length_val = float(length)
                        width_val = float(width)
                        
                        if length_val <= 0 or width_val <= 0:
                            flash('Dimensions must be greater than zero.', 'error')
                            raise ValueError('Invalid dimensions')
                        
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
                            'input_method': 'dimensions',
                            'validation': validation
                        }
                        
                        rooms.append(room_data)
                        session['fp_rooms'] = rooms
                        flash(f'{room_type} added successfully!', 'success')
                        
                    except (ValueError, TypeError) as e:
                        flash('Please enter valid numbers for dimensions.', 'error')
                else:
                    flash('Please fill in all required fields.', 'error')
            
            elif action == 'remove_room':
                try:
                    room_index = int(request.form.get('room_index', -1))
                    if 0 <= room_index < len(rooms):
                        removed = rooms.pop(room_index)
                        session['fp_rooms'] = rooms
                        flash(f'{removed.get("room_type", "Room")} removed.', 'info')
                    else:
                        flash('Invalid room selection.', 'error')
                except (ValueError, TypeError):
                    flash('Failed to remove room.', 'error')
            
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
    except Exception as exc:
        current_app.logger.exception('Room input failed: %s', exc)
        flash('An unexpected error occurred. Please try again.', 'error')
        return redirect(url_for('floor_plan.start'))


@floor_plan_bp.route('/results')
def results():
    """Final dashboard with efficiency scores."""
    try:
        if 'fp_unit_system' not in session or 'fp_rooms' not in session:
            return redirect(url_for('floor_plan.start'))

        rooms = session.get('fp_rooms', [])
        if len(rooms) < 3:
            flash('Please add at least 3 rooms for analysis.', 'warning')
            return redirect(url_for('floor_plan.room_input'))

        unit_system = session.get('fp_unit_system', 'metric')
        budget = session.get('fp_budget')
        country = session.get('fp_country', 'International')

        # Backward compatibility: ensure each room has a display-safe `area` value
        # (older sessions/tests may only store `area_m2`).
        normalized_rooms = []
        for r in rooms:
            if not isinstance(r, dict):
                normalized_rooms.append(r)
                continue

            rr = dict(r)
            if rr.get('area') is None:
                area_m2 = float(rr.get('area_m2') or 0)
                rr['area'] = area_m2 if unit_system == 'metric' else area_m2 * 10.7639
            normalized_rooms.append(rr)

        rooms = normalized_rooms
        session['fp_rooms'] = rooms

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
    except Exception as exc:
        try:
            current_app.logger.exception('Floor plan analyzer results failed: %s', exc)
            from app.services.analytics.request_logging import log_analyzer_event
            from flask import g

            log_analyzer_event(event=getattr(g, 'analytics_event', None), event_type='error', detail=str(exc))
        except Exception:
            pass
        flash('We hit a temporary error while building your results. Please try again.', 'warning')
        return redirect(url_for('floor_plan.room_input'))


@floor_plan_bp.route('/report/generate', methods=['POST'])
def generate_report():
    """Generate professional PDF optimization report - FREE."""
    if 'fp_rooms' not in session:
        return jsonify({'error': 'No analysis data found'}), 400
    
    try:
        rooms = session.get('fp_rooms', [])
        unit_system = session.get('fp_unit_system', 'metric')
        budget = session.get('fp_budget')
        country = session.get('fp_country', 'International')
        
        # Log PDF generation event
        try:
            from app.services.analytics.request_logging import log_analyzer_event
            from flask import g
            log_analyzer_event(
                event=getattr(g, 'analytics_event', None),
                event_type='pdf_generated',
                detail=f"Generated PDF for {len(rooms)} rooms, {unit_system} units"
            )
        except Exception:
            pass
        
        # Generate professional architectural report
        output_dir = Path(current_app.instance_path) / 'floor_plan_reports'
        pdf_path = generate_optimization_report(rooms, unit_system, budget, country, output_dir=output_dir)

        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=pdf_path.name,
            mimetype='application/pdf',
            max_age=0,
        )
    except Exception as exc:
        current_app.logger.exception('PDF generation failed: %s', exc)
        flash('Failed to generate PDF report. Please try again.', 'error')
        return redirect(url_for('floor_plan.results'))


@floor_plan_bp.route('/update-rooms', methods=['POST'])
def update_rooms():
    """Update rooms from editable results table and recalculate analysis."""
    try:
        data = request.get_json()
        rooms_data = data.get('rooms', [])
        
        if len(rooms_data) < 3:
            return jsonify({'success': False, 'error': 'At least 3 rooms required'}), 400
        
        unit_system = session.get('fp_unit_system', 'metric')
        updated_rooms = []
        
        for room_data in rooms_data:
            room_type = room_data.get('type', '').strip()
            
            # Get input method from original room or assume dimensions
            input_method = room_data.get('input_method', 'dimensions')
            
            # Get length and width, handling None values safely
            length_val = room_data.get('length')
            width_val = room_data.get('width')
            
            # Skip invalid entries
            if not room_type:
                continue
            
            # Handle dimension-based rooms (editable)
            if input_method == 'dimensions' and length_val is not None and width_val is not None:
                try:
                    length = float(length_val)
                    width = float(width_val)
                    
                    if length <= 0 or width <= 0:
                        continue
                    
                    # Convert to metric for internal storage
                    length_m, width_m = convert_to_metric(length, width, unit_system)
                    area_m2 = length_m * width_m
                    
                    # Validate against standards
                    validation = validate_room_dimensions(room_type, length_m, width_m, area_m2)
                    
                    # Calculate display area based on user's unit system
                    display_area = area_m2 if unit_system == 'metric' else area_m2 * 10.7639
                    
                    room_obj = {
                        'type': room_type,
                        'room_type': room_type,
                        'length': length,
                        'width': width,
                        'length_m': length_m,
                        'width_m': width_m,
                        'area': display_area,
                        'area_m2': area_m2,
                        'input_method': 'dimensions',
                        'validation': validation
                    }
                    updated_rooms.append(room_obj)
                except (ValueError, TypeError):
                    # Skip invalid numeric values
                    continue
            
            # Handle surface-based rooms (read-only, preserve original data)
            elif input_method == 'surface':
                # Preserve the original surface-based room
                area_m2 = float(room_data.get('area_m2', 0))
                if area_m2 <= 0:
                    continue
                
                import math
                estimated_side = math.sqrt(area_m2)
                validation = validate_room_dimensions(room_type, estimated_side, estimated_side, area_m2)
                
                display_area = area_m2 if unit_system == 'metric' else area_m2 * 10.7639
                
                room_obj = {
                    'type': room_type,
                    'room_type': room_type,
                    'length': None,
                    'width': None,
                    'length_m': None,
                    'width_m': None,
                    'area': display_area,
                    'area_m2': area_m2,
                    'input_method': 'surface',
                    'validation': validation
                }
                updated_rooms.append(room_obj)
        
        if len(updated_rooms) < 3:
            return jsonify({'success': False, 'error': 'At least 3 valid rooms required'}), 400
        
        session['fp_rooms'] = updated_rooms
        return jsonify({'success': True, 'message': 'Rooms updated successfully'})
    
    except Exception as exc:
        current_app.logger.exception('Failed to update rooms: %s', exc)
        return jsonify({'success': False, 'error': 'Failed to update rooms. Please try again.'}), 500


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
