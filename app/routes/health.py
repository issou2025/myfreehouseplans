"""
Health check endpoints for monitoring application and dependencies.

These endpoints are used by:
- Render platform to determine service health
- Monitoring tools to track uptime and dependencies
- Load balancers to route traffic only to healthy instances
"""

from flask import Blueprint, jsonify, current_app
from app.extensions import db
from sqlalchemy import text
from datetime import datetime
import os


health_bp = Blueprint('health', __name__)


@health_bp.route('/health')
def health_check():
    """
    Lightweight health check for load balancer probes.
    
    Returns 200 OK if the application is running.
    Does NOT check database connectivity to keep response time low.
    
    Use this for:
    - Render health checks
    - Load balancer probes
    - Uptime monitoring
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'myfreehouseplan',
    }), 200


@health_bp.route('/health/ready')
def readiness_check():
    """
    Comprehensive readiness check including database connectivity.
    
    Returns 200 OK only if:
    - Application is running
    - Database is reachable
    - Required tables exist
    
    Use this for:
    - Deployment verification
    - Pre-traffic health checks
    - Smoke tests after migrations
    """
    checks = {
        'application': 'healthy',
        'database': 'unknown',
        'timestamp': datetime.utcnow().isoformat(),
    }
    
    status_code = 200
    
    # Check database connectivity
    try:
        # Simple query to verify database is responsive
        db.session.execute(text('SELECT 1'))
        db.session.commit()
        checks['database'] = 'healthy'
    except Exception as exc:
        checks['database'] = 'unhealthy'
        checks['database_error'] = str(exc)
        status_code = 503
        current_app.logger.error('Database health check failed: %s', exc, exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass
    
    # Check critical tables exist
    if checks['database'] == 'healthy':
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = set(inspector.get_table_names())
            required = {'users', 'house_plans', 'categories'}
            missing = required - tables
            
            if missing:
                checks['schema'] = 'incomplete'
                checks['missing_tables'] = list(missing)
                status_code = 503
            else:
                checks['schema'] = 'complete'
        except Exception as exc:
            checks['schema'] = 'unknown'
            checks['schema_error'] = str(exc)
            current_app.logger.error('Schema health check failed: %s', exc, exc_info=True)
    
    checks['overall'] = 'healthy' if status_code == 200 else 'unhealthy'
    
    return jsonify(checks), status_code


@health_bp.route('/health/live')
def liveness_check():
    """
    Liveness probe for container orchestration.
    
    Returns 200 OK if the process is alive.
    Used by Kubernetes/Docker to determine if container should be restarted.
    """
    return jsonify({
        'status': 'alive',
        'pid': os.getpid(),
        'timestamp': datetime.utcnow().isoformat(),
    }), 200
