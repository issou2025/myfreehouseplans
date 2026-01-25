"""
Visit Tracking and Analytics Reporting Service

This module implements a lightweight visit tracking system that:
1. Captures user visits without blocking requests
2. Batches visit data in memory
3. Reports to an external API every 30 minutes using a background thread

Usage:
    from app.services.visit_tracker import init_visit_tracking
    
    # In app factory (app/__init__.py):
    init_visit_tracking(app)
"""

import threading
import time
import requests
from datetime import datetime
from flask import request, g
from collections import defaultdict
import logging

# In-memory storage for visit batching (thread-safe)
_visit_data_lock = threading.Lock()
_visit_data = defaultdict(lambda: {
    'count': 0,
    'paths': defaultdict(int),
    'user_agents': defaultdict(int),
    'countries': defaultdict(int)
})

# Configuration
API_ENDPOINT = None  # Set this via app.config or environment variable
REPORTING_INTERVAL = 1800  # 30 minutes in seconds
BACKGROUND_THREAD = None
SHUTDOWN_FLAG = threading.Event()

logger = logging.getLogger(__name__)


def track_visit():
    """
    Record a visit (called via before_request hook).
    Non-blocking, thread-safe.
    """
    try:
        # Extract visit metadata
        path = request.path
        user_agent = request.headers.get('User-Agent', 'Unknown')[:100]
        country = g.get('visitor_country', 'Unknown')  # From GeoIP if available
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        
        # Batch the visit data
        with _visit_data_lock:
            hour_bucket = datetime.utcnow().strftime('%Y-%m-%d %H')
            _visit_data[hour_bucket]['count'] += 1
            _visit_data[hour_bucket]['paths'][path] += 1
            _visit_data[hour_bucket]['user_agents'][user_agent] += 1
            _visit_data[hour_bucket]['countries'][country] += 1
            
    except Exception as e:
        # Never crash the request due to tracking errors
        logger.error(f'Visit tracking error: {e}', exc_info=True)


def report_to_api():
    """
    Send batched visit data to external API.
    Runs in background thread every 30 minutes.
    """
    global API_ENDPOINT
    
    while not SHUTDOWN_FLAG.is_set():
        try:
            # Wait for 30 minutes or until shutdown
            if SHUTDOWN_FLAG.wait(timeout=REPORTING_INTERVAL):
                break
            
            if not API_ENDPOINT:
                logger.warning('Visit tracking API endpoint not configured. Skipping report.')
                continue
            
            # Collect and clear current data
            with _visit_data_lock:
                if not _visit_data:
                    logger.info('No visit data to report.')
                    continue
                
                # Make a copy and clear the buffer
                data_to_send = dict(_visit_data)
                _visit_data.clear()
            
            # Prepare payload
            payload = {
                'timestamp': datetime.utcnow().isoformat(),
                'reporting_interval_seconds': REPORTING_INTERVAL,
                'data': data_to_send
            }
            
            # Send to API (non-blocking, with timeout)
            logger.info(f'Sending visit report to {API_ENDPOINT}...')
            response = requests.post(
                API_ENDPOINT,
                json=payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.info(f'Visit report sent successfully: {len(data_to_send)} time buckets')
            else:
                logger.error(f'API returned status {response.status_code}: {response.text}')
                
        except requests.RequestException as e:
            logger.error(f'Failed to send visit report: {e}', exc_info=True)
        except Exception as e:
            logger.error(f'Unexpected error in visit reporting: {e}', exc_info=True)


def init_visit_tracking(app):
    """
    Initialize visit tracking system.
    
    Args:
        app: Flask application instance
        
    Configuration (set in app.config or environment):
        - VISIT_TRACKING_API: External API endpoint URL
        - VISIT_TRACKING_ENABLED: Boolean to enable/disable tracking
        - VISIT_TRACKING_INTERVAL: Reporting interval in seconds (default 1800)
    """
    global API_ENDPOINT, REPORTING_INTERVAL, BACKGROUND_THREAD
    
    # Load configuration
    enabled = app.config.get('VISIT_TRACKING_ENABLED', False)
    API_ENDPOINT = app.config.get('VISIT_TRACKING_API', None)
    REPORTING_INTERVAL = app.config.get('VISIT_TRACKING_INTERVAL', 1800)
    
    if not enabled:
        app.logger.info('Visit tracking is disabled.')
        return
    
    if not API_ENDPOINT:
        app.logger.warning('Visit tracking enabled but no API endpoint configured.')
        return
    
    # Register before_request hook to track visits
    @app.before_request
    def _track_visit():
        # Skip tracking for static files and health checks
        if request.path.startswith('/static/') or request.path == '/health':
            return
        track_visit()
    
    # Start background reporting thread
    BACKGROUND_THREAD = threading.Thread(
        target=report_to_api,
        daemon=True,  # Thread will die when main process dies
        name='VisitTrackingReporter'
    )
    BACKGROUND_THREAD.start()
    app.logger.info(f'Visit tracking initialized. Reporting to {API_ENDPOINT} every {REPORTING_INTERVAL}s')
    
    # Register shutdown handler
    @app.teardown_appcontext
    def _shutdown_tracking(exc):
        """Gracefully shutdown tracking on app teardown."""
        if exc:
            pass  # Already logged elsewhere
        # Note: SHUTDOWN_FLAG.set() should be called in a proper shutdown hook
        # For now, the daemon thread will terminate when the app exits


def shutdown_tracking():
    """
    Gracefully shutdown the tracking system.
    Call this in your app's shutdown sequence.
    """
    global BACKGROUND_THREAD
    
    logger.info('Shutting down visit tracking...')
    SHUTDOWN_FLAG.set()
    
    if BACKGROUND_THREAD and BACKGROUND_THREAD.is_alive():
        BACKGROUND_THREAD.join(timeout=5)
        logger.info('Visit tracking thread stopped.')
