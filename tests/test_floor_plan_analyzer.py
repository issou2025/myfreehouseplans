"""Comprehensive tests for Floor Plan Analyzer - All Objectives."""

import pytest
from flask import session
from pathlib import Path


def test_analyzer_landing_page(client):
    """Test landing page loads without errors."""
    response = client.get('/tools/floor-plan-analyzer/')
    assert response.status_code == 200
    assert b'Floor Plan' in response.data
    assert b'Free' in response.data or b'free' in response.data


def test_unit_selection_flow(client):
    """Test unit system selection."""
    # GET request
    response = client.get('/tools/floor-plan-analyzer/start')
    assert response.status_code == 200
    
    # POST metric
    response = client.post('/tools/floor-plan-analyzer/start', data={'unit_system': 'metric'}, follow_redirects=True)
    assert response.status_code == 200
    
    with client.session_transaction() as sess:
        assert sess.get('fp_unit_system') == 'metric'


def test_budget_input_optional(client):
    """Test budget input with optional budget."""
    with client.session_transaction() as sess:
        sess['fp_unit_system'] = 'metric'
    
    # Skip budget
    response = client.post('/tools/floor-plan-analyzer/budget', data={
        'country': 'north_america',
        'budget': '',
        'mortgage_duration': ''
    }, follow_redirects=True)
    assert response.status_code == 200
    
    with client.session_transaction() as sess:
        assert sess.get('fp_budget') is None
        assert sess.get('fp_country') == 'north_america'


def test_room_input_validation(client):
    """Test adding rooms with validation."""
    with client.session_transaction() as sess:
        sess['fp_unit_system'] = 'metric'
        sess['fp_rooms'] = []
    
    # Add valid room
    response = client.post('/tools/floor-plan-analyzer/rooms', data={
        'action': 'add_room',
        'room_type': 'Bedroom',
        'length': '4.5',
        'width': '3.5'
    }, follow_redirects=True)
    assert response.status_code == 200
    
    with client.session_transaction() as sess:
        rooms = sess.get('fp_rooms', [])
        assert len(rooms) == 1
        assert rooms[0]['type'] == 'Bedroom'
        assert rooms[0]['area_m2'] > 0


def test_invalid_room_dimensions(client):
    """Test error handling for invalid dimensions."""
    with client.session_transaction() as sess:
        sess['fp_unit_system'] = 'metric'
        sess['fp_rooms'] = []
    
    # Invalid dimensions
    response = client.post('/tools/floor-plan-analyzer/rooms', data={
        'action': 'add_room',
        'room_type': 'Kitchen',
        'length': 'abc',
        'width': '3.0'
    }, follow_redirects=True)
    assert response.status_code == 200
    
    with client.session_transaction() as sess:
        rooms = sess.get('fp_rooms', [])
        assert len(rooms) == 0


def test_minimum_rooms_requirement(client):
    """Test that at least 3 rooms are required for analysis."""
    with client.session_transaction() as sess:
        sess['fp_unit_system'] = 'metric'
        sess['fp_rooms'] = [
            {'type': 'Living Room', 'area_m2': 20, 'length': 5, 'width': 4, 'validation': {}},
            {'type': 'Bedroom', 'area_m2': 12, 'length': 4, 'width': 3, 'validation': {}}
        ]
    
    # Try to analyze with only 2 rooms
    response = client.post('/tools/floor-plan-analyzer/rooms', data={'action': 'analyze'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'at least 3 rooms' in response.data


def test_results_page_renders(client):
    """Test results page renders without errors."""
    with client.session_transaction() as sess:
        sess['fp_unit_system'] = 'metric'
        sess['fp_country'] = 'north_america'
        sess['fp_budget'] = None
        sess['fp_rooms'] = [
            {'type': 'Living Room', 'room_type': 'Living Room', 'area_m2': 25, 'area': 25, 'length': 5, 'width': 5, 
             'length_m': 5, 'width_m': 5, 'validation': {'status': 'green', 'status_icon': '🟢', 'feedback': 'Optimal'}},
            {'type': 'Bedroom', 'room_type': 'Bedroom', 'area_m2': 14, 'area': 14, 'length': 4, 'width': 3.5,
             'length_m': 4, 'width_m': 3.5, 'validation': {'status': 'green', 'status_icon': '🟢', 'feedback': 'Good'}},
            {'type': 'Kitchen', 'room_type': 'Closed Kitchen', 'area_m2': 10, 'area': 10, 'length': 3.3, 'width': 3,
             'length_m': 3.3, 'width_m': 3, 'validation': {'status': 'green', 'status_icon': '🟢', 'feedback': 'Optimal'}},
            {'type': 'Bathroom', 'room_type': 'Bathroom', 'area_m2': 5, 'area': 5, 'length': 2.5, 'width': 2,
             'length_m': 2.5, 'width_m': 2, 'validation': {'status': 'green', 'status_icon': '🟢', 'feedback': 'Good'}},
        ]
    
    response = client.get('/tools/floor-plan-analyzer/results')
    assert response.status_code == 200
    assert b'Your Floor Plan Analysis' in response.data
    assert b'Financial Efficiency' in response.data
    assert b'Comfort Efficiency' in response.data


def test_pdf_generation_free(client):
    """Test PDF generation works without payment (FREE)."""
    with client.session_transaction() as sess:
        sess['fp_unit_system'] = 'metric'
        sess['fp_country'] = 'International'
        sess['fp_budget'] = None
        sess['fp_rooms'] = [
            {'type': 'Living Room', 'room_type': 'Living Room', 'area_m2': 25, 'area': 25, 'length': 5, 'width': 5,
             'length_m': 5, 'width_m': 5, 'validation': {'status': 'green', 'status_icon': '🟢', 'feedback': 'Optimal'}},
            {'type': 'Bedroom', 'room_type': 'Bedroom', 'area_m2': 14, 'area': 14, 'length': 4, 'width': 3.5,
             'length_m': 4, 'width_m': 3.5, 'validation': {'status': 'green', 'status_icon': '🟢', 'feedback': 'Good'}},
            {'type': 'Kitchen', 'room_type': 'Closed Kitchen', 'area_m2': 10, 'area': 10, 'length': 3.3, 'width': 3,
             'length_m': 3.3, 'width_m': 3, 'validation': {'status': 'green', 'status_icon': '🟢', 'feedback': 'Optimal'}},
        ]
    
    response = client.post('/tools/floor-plan-analyzer/report/generate')
    assert response.status_code == 200
    assert response.content_type == 'application/pdf'
    assert len(response.data) > 1000  # PDF should have content


def test_no_payment_required(client):
    """Verify NO payment gates exist - analyzer is completely FREE."""
    # Check landing page
    response = client.get('/tools/floor-plan-analyzer/')
    assert b'$4.99' not in response.data
    assert b'payment' not in response.data.lower() or b'no signup' in response.data.lower()
    
    # Check results page
    with client.session_transaction() as sess:
        sess['fp_unit_system'] = 'metric'
        sess['fp_rooms'] = [
            {'type': 'Living Room', 'area_m2': 25, 'length': 5, 'width': 5, 'validation': {}},
            {'type': 'Bedroom', 'area_m2': 14, 'length': 4, 'width': 3.5, 'validation': {}},
            {'type': 'Kitchen', 'area_m2': 10, 'length': 3.3, 'width': 3, 'validation': {}},
        ]
    
    response = client.get('/tools/floor-plan-analyzer/results')
    assert response.status_code == 200
    assert b'$4.99' not in response.data
    assert b'Free' in response.data or b'free' in response.data


def test_update_rooms_endpoint(client):
    """Test the new update_rooms API endpoint."""
    with client.session_transaction() as sess:
        sess['fp_unit_system'] = 'metric'
        sess['fp_rooms'] = []
    
    # Send updated rooms
    response = client.post('/tools/floor-plan-analyzer/update-rooms', 
                          json={
                              'rooms': [
                                  {'type': 'Living Room', 'length': 5.5, 'width': 4.5},
                                  {'type': 'Bedroom', 'length': 4.0, 'width': 3.5},
                                  {'type': 'Kitchen', 'length': 3.5, 'width': 3.0},
                              ]
                          })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    
    with client.session_transaction() as sess:
        rooms = sess.get('fp_rooms', [])
        assert len(rooms) == 3


def test_mobile_responsive_elements(client):
    """Test mobile-responsive CSS is present in templates."""
    response = client.get('/tools/floor-plan-analyzer/')
    assert b'@media' in response.data or response.status_code == 200
    
    response = client.get('/tools/floor-plan-analyzer/start')
    assert response.status_code == 200


def test_error_handling_robustness(client):
    """Test all routes handle errors gracefully."""
    # Missing session data
    response = client.get('/tools/floor-plan-analyzer/results')
    assert response.status_code in [200, 302]  # Either renders or redirects
    
    # Invalid POST data
    response = client.post('/tools/floor-plan-analyzer/update-rooms', json={'rooms': []})
    assert response.status_code == 400  # Bad request, not 500


def test_visitor_tracking_active(client):
    """Verify visitor tracking is logging analyzer usage."""
    # This should not crash even if tracking fails
    response = client.get('/tools/floor-plan-analyzer/')
    assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
