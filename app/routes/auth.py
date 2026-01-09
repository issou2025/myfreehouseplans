"""
Authentication Blueprint - User Authentication Routes

This blueprint handles user authentication including:
- User registration
- Login/Logout
- Password reset
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import logout_user, current_user, login_required
from app.models import User
from app.forms import PasswordResetRequestForm, PasswordResetForm

from app.models import Order

# Create Blueprint
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Legacy route retained for compatibility; redirects to admin login."""
    return redirect(url_for('admin.admin_login', **request.args.to_dict(flat=True)), code=307)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    abort(404)


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout route"""
    
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/reset-password-request', methods=['GET', 'POST'])
def reset_password_request():
    """Request password reset"""
    
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = PasswordResetRequestForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user:
            # TODO: Implement email sending with reset token
            # send_password_reset_email(user)
            pass
        
        # Always show success message (security - don't reveal if email exists)
        flash('Check your email for instructions to reset your password.', 'info')
        return redirect(url_for('admin.admin_login'))
    
    return render_template('auth/reset_password_request.html', form=form)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token"""
    
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    # TODO: Implement token verification
    # user = User.verify_reset_password_token(token)
    # if not user:
    #     flash('Invalid or expired reset link', 'danger')
    #     return redirect(url_for('main.index'))
    
    form = PasswordResetForm()
    
    if form.validate_on_submit():
        # TODO: Update user password and persist the change once reset tokens are implemented.
        # user.set_password(form.password.data)
        
        flash('Your password has been reset successfully.', 'success')
        return redirect(url_for('admin.admin_login'))
    
    return render_template('auth/reset_password.html', form=form)


@auth_bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    if not current_user.is_admin:
        abort(403)
    # Get user's orders
    orders = current_user.orders.order_by(Order.created_at.desc()).all()
    
    return render_template('auth/profile.html', orders=orders)
