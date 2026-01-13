"""
Database resilience utilities for handling transient connection issues.

This module provides decorators and utilities for automatic retry logic
on database operations that may fail due to network issues, connection
pool exhaustion, or other transient failures.
"""

import functools
import time
from flask import current_app
from sqlalchemy.exc import OperationalError, IntegrityError, DBAPIError
from app.extensions import db


def with_db_resilience(max_retries=2, backoff_ms=100):
    """
    Decorator that adds automatic retry logic for database operations.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 2)
        backoff_ms: Milliseconds to wait between retries (default: 100)
    
    Usage:
        @with_db_resilience(max_retries=3, backoff_ms=200)
        def my_database_query():
            return User.query.all()
    
    The decorator will:
    1. Catch transient database errors (OperationalError, DBAPIError)
    2. Rollback the session to clean state
    3. Dispose stale connections from the pool
    4. Retry the operation with exponential backoff
    5. Log all attempts for debugging
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, DBAPIError) as exc:
                    last_exception = exc
                    
                    # Always rollback to prevent transaction contamination
                    try:
                        db.session.rollback()
                    except Exception as rollback_exc:
                        current_app.logger.error(
                            'Failed to rollback session after DB error: %s',
                            rollback_exc,
                            exc_info=True
                        )
                    
                    # On last attempt, don't retry
                    if attempt >= max_retries:
                        current_app.logger.error(
                            'Database operation failed after %d attempts in %s: %s',
                            max_retries + 1,
                            func.__name__,
                            exc,
                            exc_info=True
                        )
                        raise
                    
                    # Dispose stale connections to force pool refresh
                    try:
                        db.engine.dispose()
                        current_app.logger.warning(
                            'DB connection pool disposed after error in %s (attempt %d/%d): %s',
                            func.__name__,
                            attempt + 1,
                            max_retries + 1,
                            str(exc)
                        )
                    except Exception as dispose_exc:
                        current_app.logger.error(
                            'Failed to dispose engine after DB error: %s',
                            dispose_exc,
                            exc_info=True
                        )
                    
                    # Exponential backoff
                    if backoff_ms > 0:
                        sleep_time = backoff_ms * (2 ** attempt) / 1000.0
                        time.sleep(sleep_time)
            
            # Should never reach here, but handle it anyway
            raise last_exception or RuntimeError('Unexpected retry loop exit')
        
        return wrapper
    return decorator


def safe_db_query(query_func, default=None, log_errors=True):
    """
    Execute a database query with automatic error handling and fallback.
    
    Args:
        query_func: Callable that performs the database query
        default: Value to return if query fails (default: None)
        log_errors: Whether to log errors (default: True)
    
    Returns:
        Query result on success, default value on failure
    
    Usage:
        users = safe_db_query(
            lambda: User.query.filter_by(is_active=True).all(),
            default=[],
            log_errors=True
        )
    """
    try:
        result = query_func()
        return result
    except Exception as exc:
        if log_errors:
            current_app.logger.error(
                'Database query failed: %s',
                exc,
                exc_info=True
            )
        db.session.rollback()
        return default
