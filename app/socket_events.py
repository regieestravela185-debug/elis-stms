"""
SocketIO Event Handlers for Real-Time Updates
"""
from flask import request
from flask_login import current_user
from flask_socketio import emit, join_room, leave_room, disconnect
from datetime import date, timedelta

from .extensions import socketio, db
from .models import Unit, UnitStatus, TenantProfile, Payment, Role


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    if current_user.is_authenticated:
        print(f"Client connected: {current_user.email} (Role: {current_user.role.value})")
        
        # Join role-specific room
        if current_user.role == Role.ADMIN:
            join_room('admin')
            emit('connection_status', {'status': 'connected', 'role': 'admin'})
        elif current_user.role == Role.TENANT:
            join_room('tenant')
            join_room(f'tenant_{current_user.id}')  # Personal room
            emit('connection_status', {'status': 'connected', 'role': 'tenant'})
    else:
        print("Unauthenticated client attempted to connect")
        disconnect()


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    if current_user.is_authenticated:
        print(f"Client disconnected: {current_user.email}")


@socketio.on('request_unit_status')
def handle_unit_status_request():
    """Handle request for current unit status (Admin only)"""
    if not current_user.is_authenticated or current_user.role != Role.ADMIN:
        emit('error', {'message': 'Unauthorized'})
        return
    
    # Get all units with unpaid detection
    units_data, stats = get_units_with_unpaid_check()
    
    emit('unit_status_update', {
        'units': units_data,
        'stats': stats,
        'timestamp': date.today().isoformat()
    })


@socketio.on('request_dashboard_metrics')
def handle_dashboard_metrics_request():
    """Handle request for dashboard metrics"""
    if not current_user.is_authenticated or current_user.role != Role.ADMIN:
        emit('error', {'message': 'Unauthorized'})
        return
    
    from .models import Concern, ConcernStatus, RenewalRequest, RenewalRequestStatus, Feedback, FeedbackStatus
    
    # Get real-time metrics
    metrics = {
        'pending_concerns': db.session.query(Concern).filter(
            Concern.status != ConcernStatus.RESOLVED
        ).count(),
        'pending_renewals': db.session.query(RenewalRequest).filter(
            RenewalRequest.status == RenewalRequestStatus.PENDING
        ).count(),
        'pending_feedbacks': db.session.query(Feedback).filter(
            Feedback.status == FeedbackStatus.SUBMITTED
        ).count(),
        'total_tenants': db.session.query(TenantProfile).count(),
        'timestamp': date.today().isoformat()
    }
    
    emit('dashboard_metrics_update', metrics)


def get_units_with_unpaid_check():
    """Get all units and check for unpaid tenants"""
    # Exclude archived units
    units = db.session.query(Unit).filter(Unit.is_archived == False).all()
    
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    
    units_data = []
    stats = {
        'available': 0,
        'occupied': 0,
        'reserved': 0,
        'unpaid': 0
    }
    
    for unit in units:
        current_status = unit.status.value
        
        # If unit is occupied, check if tenant has paid in the last 30 days
        if unit.status == UnitStatus.OCCUPIED:
            tenant = db.session.query(TenantProfile).filter(
                TenantProfile.unit_id == unit.id,
                TenantProfile.is_active == True
            ).first()
            
            if tenant:
                # Check for recent payment
                recent_payment = db.session.query(Payment).filter(
                    Payment.tenant_profile_id == tenant.id,
                    Payment.paid_at >= thirty_days_ago
                ).first()
                
                # If no recent payment, mark as unpaid
                if not recent_payment:
                    if unit.status != UnitStatus.UNPAID:
                        unit.status = UnitStatus.UNPAID
                        db.session.commit()
                    current_status = 'unpaid'
                else:
                    # If there's a recent payment and status is unpaid, change back to occupied
                    if unit.status == UnitStatus.UNPAID:
                        unit.status = UnitStatus.OCCUPIED
                        db.session.commit()
                        current_status = 'occupied'
        
        units_data.append({
            'id': unit.id,
            'status': current_status
        })
        
        # Update stats
        stats[current_status] = stats.get(current_status, 0) + 1
    
    return units_data, stats


def emit_unit_status_update():
    """Emit unit status update to all admin clients"""
    units_data, stats = get_units_with_unpaid_check()
    
    socketio.emit('unit_status_update', {
        'units': units_data,
        'stats': stats,
        'timestamp': date.today().isoformat()
    }, room='admin')


def emit_dashboard_metrics_update():
    """Emit dashboard metrics update to all admin clients"""
    from .models import Concern, ConcernStatus, RenewalRequest, RenewalRequestStatus, Feedback, FeedbackStatus
    
    metrics = {
        'pending_concerns': db.session.query(Concern).filter(
            Concern.status != ConcernStatus.RESOLVED
        ).count(),
        'pending_renewals': db.session.query(RenewalRequest).filter(
            RenewalRequest.status == RenewalRequestStatus.PENDING
        ).count(),
        'pending_feedbacks': db.session.query(Feedback).filter(
            Feedback.status == FeedbackStatus.SUBMITTED
        ).count(),
        'total_tenants': db.session.query(TenantProfile).count(),
        'timestamp': date.today().isoformat()
    }
    
    socketio.emit('dashboard_metrics_update', metrics, room='admin')


def emit_payment_notification(tenant_profile_id, payment_data):
    """Emit payment notification to specific tenant and all admins"""
    # Notify tenant
    socketio.emit('payment_received', payment_data, room=f'tenant_{tenant_profile_id}')
    
    # Notify all admins
    socketio.emit('new_payment', payment_data, room='admin')
    
    # Trigger unit status update
    emit_unit_status_update()


def emit_concern_notification(concern_data):
    """Emit new concern notification to admins"""
    socketio.emit('new_concern', concern_data, room='admin')
    emit_dashboard_metrics_update()


def emit_renewal_notification(renewal_data):
    """Emit new renewal request notification to admins"""
    socketio.emit('new_renewal', renewal_data, room='admin')
    emit_dashboard_metrics_update()


def emit_feedback_notification(feedback_data):
    """Emit new feedback notification to admins"""
    socketio.emit('new_feedback', feedback_data, room='admin')
    emit_dashboard_metrics_update()


def emit_announcement_notification(announcement_data):
    """Emit a new-announcement notification to every connected tenant."""
    socketio.emit('new_announcement', announcement_data, room='tenant')


def emit_document_notification(user_id, document_data):
    """Emit a new-document notification to one specific tenant (by User.id)."""
    socketio.emit('new_document', document_data, room=f'tenant_{user_id}')
