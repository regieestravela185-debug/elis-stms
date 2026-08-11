// Setup SocketIO real-time updates for admin dashboard
function setupAdminSocketIO() {
  if (!window.socket) {
    console.error('❌ SocketIO not initialized');
    return;
  }
  
  console.log('🔌 Setting up SocketIO listeners for admin dashboard...');
  
  // Listen for dashboard metrics updates
  window.socket.on('dashboard_metrics_update', function(data) {
    console.log('📡 Received dashboard metrics update:', data);
    
    if (data.pending_concerns !== undefined) {
      const el = document.querySelector('[href*="concerns"] .metric__num, #pending-concerns-count');
      if (el) {
        animateNumberChange(el, data.pending_concerns);
      }
    }
    
    if (data.pending_renewals !== undefined) {
      const el = document.querySelector('[href*="renewals"] .metric__num, #pending-renewals-count');
      if (el) {
        animateNumberChange(el, data.pending_renewals);
      }
    }
    
    if (data.pending_feedbacks !== undefined) {
      const el = document.querySelector('[href*="feedbacks"] .metric__num, #pending-feedbacks-count');
      if (el) {
        animateNumberChange(el, data.pending_feedbacks);
      }
    }
    
    if (data.total_tenants !== undefined) {
      const el = document.getElementById('m_total_tenants');
      if (el) {
        animateNumberChange(el, data.total_tenants);
      }
    }
  });
  
  // Listen for new payment notifications
  window.socket.on('new_payment', function(data) {
    console.log('💰 New payment received:', data);
    showNotification('New Payment', `Payment received: ₱${data.amount}`, 'success');
    
    // Request updated metrics
    window.socket.emit('request_dashboard_metrics');
  });
  
  // Listen for new concern notifications
  window.socket.on('new_concern', function(data) {
    console.log('🔔 New concern submitted:', data);
    showNotification('New Concern', data.subject || 'A new concern has been submitted', 'info');
    
    // Request updated metrics
    window.socket.emit('request_dashboard_metrics');
  });
  
  // Listen for new renewal notifications
  window.socket.on('new_renewal', function(data) {
    console.log('🔄 New renewal request:', data);
    showNotification('New Renewal Request', 'A tenant has requested contract renewal', 'info');
    
    // Request updated metrics
    window.socket.emit('request_dashboard_metrics');
  });
  
  // Listen for new feedback notifications
  window.socket.on('new_feedback', function(data) {
    console.log('⭐ New feedback submitted:', data);
    showNotification('New Feedback', 'A tenant has submitted feedback', 'info');
    
    // Request updated metrics
    window.socket.emit('request_dashboard_metrics');
  });
  
  // Request initial metrics
  window.socket.emit('request_dashboard_metrics');
  console.log('📤 Requested initial dashboard metrics');
}

// Animate number changes
function animateNumberChange(element, newValue) {
  const currentValue = parseInt(element.textContent) || 0;
  
  if (currentValue !== newValue) {
    element.style.transform = 'scale(1.2)';
    element.style.color = '#D7B35B';
    
    setTimeout(() => {
      element.textContent = newValue;
      element.style.transform = 'scale(1)';
      element.style.color = '';
    }, 200);
  }
}

// Show notification (simple toast)
function showNotification(title, message, type = 'info') {
  // Check if notification container exists, if not create it
  let container = document.getElementById('notification-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'notification-container';
    container.style.cssText = 'position: fixed; top: 80px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 12px;';
    document.body.appendChild(container);
  }
  
  const notification = document.createElement('div');
  notification.style.cssText = `
    background: ${type === 'success' ? '#40c978' : type === 'error' ? '#ff5050' : '#D7B35B'};
    color: white;
    padding: 16px 20px;
    border-radius: 12px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    min-width: 300px;
    max-width: 400px;
    animation: slideInRight 0.3s ease;
    font-family: 'Inter', sans-serif;
  `;
  
  notification.innerHTML = `
    <div style="font-weight: 700; font-size: 14px; margin-bottom: 4px;">${title}</div>
    <div style="font-size: 13px; opacity: 0.95;">${message}</div>
  `;
  
  container.appendChild(notification);
  
  // Auto remove after 5 seconds
  setTimeout(() => {
    notification.style.animation = 'slideOutRight 0.3s ease';
    setTimeout(() => {
      notification.remove();
    }, 300);
  }, 5000);
}

// Add animation keyframes
if (!document.getElementById('notification-animations')) {
  const style = document.createElement('style');
  style.id = 'notification-animations';
  style.textContent = `
    @keyframes slideInRight {
      from {
        transform: translateX(400px);
        opacity: 0;
      }
      to {
        transform: translateX(0);
        opacity: 1;
      }
    }
    @keyframes slideOutRight {
      from {
        transform: translateX(0);
        opacity: 1;
      }
      to {
        transform: translateX(400px);
        opacity: 0;
      }
    }
  `;
  document.head.appendChild(style);
}

document.addEventListener("DOMContentLoaded", () => {
  // Setup SocketIO real-time updates
  if (window.socket) {
    // Wait for socket to connect
    if (window.socket.connected) {
      setupAdminSocketIO();
    } else {
      window.socket.on('connect', setupAdminSocketIO);
    }
  } else {
    console.error('❌ SocketIO not available');
  }
});

