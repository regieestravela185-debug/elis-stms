let currentBuilding = null;
let currentFloor = "all";

function applyFilters() {
  const tiles = document.querySelectorAll(".unit-tile");
  tiles.forEach((t) => {
    const b = t.getAttribute("data-building");
    const f = t.getAttribute("data-floor");
    const buildingMatch = !currentBuilding || b === currentBuilding;
    const floorMatch = currentFloor === "all" || f === currentFloor;
    t.style.display = buildingMatch && floorMatch ? "" : "none";
  });

  // Hide empty floor sections
  document.querySelectorAll(".floor-section").forEach((sec) => {
    const visibleTiles = sec.querySelectorAll('.unit-tile:not([style*="display: none"])');
    sec.style.display = visibleTiles.length > 0 ? "" : "none";
  });
}

function rebuildFloorPills(buildingId) {
  const bar = document.getElementById("floorFilterBar");
  if (!bar) return;

  // Collect unique floors for this building
  const floors = new Set();
  document.querySelectorAll(".unit-tile").forEach((t) => {
    if (t.getAttribute("data-building") === buildingId) {
      floors.add(t.getAttribute("data-floor"));
    }
  });

  // Clear existing pills (keep label and "All" button)
  bar.querySelectorAll(".floor-pill").forEach((p) => p.remove());

  // Add "All Floors" pill
  const allBtn = document.createElement("button");
  allBtn.className = "floor-pill" + (currentFloor === "all" ? " is-active" : "");
  allBtn.setAttribute("data-floor", "all");
  allBtn.type = "button";
  allBtn.textContent = "All Floors";
  bar.appendChild(allBtn);

  // Add floor pills sorted ascending
  Array.from(floors)
    .sort((a, b) => parseInt(a) - parseInt(b))
    .forEach((fl) => {
      const btn = document.createElement("button");
      btn.className = "floor-pill" + (currentFloor === fl ? " is-active" : "");
      btn.setAttribute("data-floor", fl);
      btn.type = "button";
      btn.textContent = fl === "0" ? "Ground" : `Floor ${fl}`;
      bar.appendChild(btn);
    });

  // Wire up clicks
  bar.querySelectorAll(".floor-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      bar.querySelectorAll(".floor-pill").forEach((p) => p.classList.remove("is-active"));
      pill.classList.add("is-active");
      currentFloor = pill.getAttribute("data-floor");
      applyFilters();
    });
  });
}

function filterByBuilding(buildingId) {
  currentBuilding = buildingId;
  currentFloor = "all";
  rebuildFloorPills(buildingId);
  applyFilters();
}

// Update unit status with animation
function updateUnitStatus(unitId, newStatus) {
  const tile = document.querySelector(`[data-unit-id="${unitId}"]`);
  if (!tile) return;
  
  const currentStatus = tile.getAttribute('data-status');
  if (currentStatus === newStatus) return; // No change
  
  // Remove old status class
  tile.classList.remove(`status-${currentStatus}`);
  
  // Add new status class
  tile.classList.add(`status-${newStatus}`);
  tile.setAttribute('data-status', newStatus);
  
  // Trigger animation
  tile.style.animation = 'none';
  setTimeout(() => {
    tile.style.animation = '';
  }, 10);
  
  // Update title
  const title = tile.getAttribute('title');
  const newTitle = title.replace(new RegExp(currentStatus, 'gi'), newStatus);
  tile.setAttribute('title', newTitle);
  
  console.log(`✅ Unit ${unitId} status updated: ${currentStatus} → ${newStatus}`);
}

// Update stats counters with animation
function updateStats(stats) {
  const statElements = {
    available: document.getElementById('stat-available'),
    occupied: document.getElementById('stat-occupied'),
    reserved: document.getElementById('stat-reserved'),
    unpaid: document.getElementById('stat-unpaid')
  };
  
  Object.keys(stats).forEach(key => {
    const element = statElements[key];
    if (!element) return;
    
    const currentValue = parseInt(element.textContent);
    const newValue = stats[key];
    
    if (currentValue !== newValue) {
      // Animate number change
      element.style.transform = 'scale(1.2)';
      element.style.color = '#D7B35B';
      
      setTimeout(() => {
        element.textContent = newValue;
        element.style.transform = 'scale(1)';
        element.style.color = '';
      }, 200);
      
      console.log(`📊 Stat updated: ${key} = ${newValue}`);
    }
  });
}

// Unit quick-info modal (opened by clicking a floorplan tile)
const STATUS_COLORS = { available: '#22c55e', occupied: '#3b82f6', reserved: '#eab308', unpaid: '#ef4444' };

function setupUnitInfoModal() {
  const modal = document.getElementById('unitInfoModal');
  const closeBtn = document.getElementById('closeUnitInfoModal');
  if (!modal || !closeBtn) return;

  const close = () => { modal.style.display = 'none'; };
  closeBtn.addEventListener('click', close);
  modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
}

function openUnitInfoModal(unitId) {
  const modal = document.getElementById('unitInfoModal');
  const content = document.getElementById('unitInfoContent');
  if (!modal || !content) return;

  content.innerHTML = '<div style="text-align:center; padding:40px 0;"><div class="spinner"></div><p class="muted">Loading unit details…</p></div>';
  modal.style.display = 'flex';

  fetch(`/admin/api/units/${unitId}/quick-info`)
    .then(res => res.json())
    .then(data => {
      if (data.error) {
        content.innerHTML = `<p class="muted">${data.error}</p>`;
        return;
      }
      const color = STATUS_COLORS[data.status] || '#64748b';
      const image = data.image_url
        ? `<img src="${data.image_url}" alt="${data.unit_code}" style="width:100%; height:160px; object-fit:cover; border-radius:10px; margin-bottom:16px;" />`
        : '';
      const tenantBlock = data.tenant
        ? `<div style="background:rgba(20,20,23,0.03); border-radius:10px; padding:14px; margin-top:14px;">
             <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:#64748b; margin-bottom:6px;">Current Tenant</div>
             <div style="font-weight:700;">${data.tenant.name}</div>
             ${data.tenant.contract_end ? `<div class="muted" style="font-size:13px; margin-top:2px;">Contract ends ${data.tenant.contract_end}</div>` : ''}
             <a href="${data.tenant.user_details_url}" class="btn btn--ghost btn--sm" style="margin-top:10px;">View Tenant Profile</a>
           </div>`
        : '';

      content.innerHTML = `
        ${image}
        <div style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
          <h3 style="margin:0;">${data.unit_code}</h3>
          <span style="background:${color}1a; color:${color}; border:1px solid ${color}40; font-weight:700; font-size:12px; padding:4px 10px; border-radius:999px; text-transform:capitalize;">${data.status}</span>
</div>
        <p class="muted" style="margin:6px 0 14px;">Building ${data.building_code || 'N/A'} &middot; Floor ${data.floor ?? '—'} ${data.type ? '&middot; ' + data.type : ''}</p>
        <div style="font-size:22px; font-weight:800; color:#D7B35B; margin-bottom:10px;">₱${data.price_monthly.toLocaleString('en-US', {minimumFractionDigits:2})} <span style="font-size:13px; font-weight:600; color:#64748b;">/ month</span></div>
        ${data.description ? `<p class="muted" style="font-size:14px; line-height:1.6;">${data.description}</p>` : ''}
        ${tenantBlock}
        <a href="${data.edit_url}" class="btn btn--primary" style="margin-top:16px; width:100%; text-align:center;">Edit Unit</a>
      `;
    })
    .catch(() => {
      content.innerHTML = '<p class="muted">Failed to load unit details. Please try again.</p>';
    });
}

// Reflects the *real* SocketIO connection state — was previously a static
// "Live Updates" label that stayed green even when the socket never connected.
function setRealtimeIndicator(state) {
  const el = document.getElementById('realtimeIndicator');
  const text = document.getElementById('realtimeIndicatorText');
  if (!el || !text) return;

  el.classList.remove('realtime-indicator--offline', 'realtime-indicator--connecting');
  if (state === 'online') {
    text.textContent = 'Live Updates';
  } else if (state === 'connecting') {
    el.classList.add('realtime-indicator--connecting');
    text.textContent = 'Connecting…';
  } else {
    el.classList.add('realtime-indicator--offline');
    text.textContent = 'Offline';
  }
}

// Setup SocketIO real-time updates
function setupSocketIO() {
  if (!window.socket) {
    console.error('❌ SocketIO not initialized');
    setRealtimeIndicator('offline');
    return;
  }

  console.log('🔌 Setting up SocketIO listeners for floorplan...');
  setRealtimeIndicator('online');

  window.socket.on('disconnect', () => setRealtimeIndicator('offline'));
  window.socket.on('connect', () => setRealtimeIndicator('online'));
  window.socket.on('connect_error', () => setRealtimeIndicator('offline'));

  // Listen for unit status updates
  window.socket.on('unit_status_update', function(data) {
    console.log('📡 Received unit status update:', data);
    
    // Update each unit
    if (data.units) {
      data.units.forEach(unit => {
        updateUnitStatus(unit.id, unit.status);
      });
    }
    
    // Update stats
    if (data.stats) {
      updateStats(data.stats);
    }
  });
  
  // Request initial status
  window.socket.emit('request_unit_status');
  console.log('📤 Requested initial unit status');
}

document.addEventListener("DOMContentLoaded", () => {
  const buttons = document.querySelectorAll(".building-btn");
  if (!buttons.length) return;

  const first = buttons[0].getAttribute("data-building");
  if (first) filterByBuilding(first);

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      const id = btn.getAttribute("data-building");
      if (id) filterByBuilding(id);
    });
  });
  
  // Add click handler for unit tiles — opens a quick-info modal
  document.querySelectorAll('.unit-tile').forEach(tile => {
    tile.addEventListener('click', () => {
      const unitId = tile.getAttribute('data-unit-id');
      if (unitId) openUnitInfoModal(unitId);
    });
  });
  setupUnitInfoModal();
  
  // Setup SocketIO real-time updates
  if (window.socket) {
    // Wait for socket to connect
    if (window.socket.connected) {
      setupSocketIO();
    } else {
      setRealtimeIndicator('connecting');
      window.socket.on('connect', setupSocketIO);
      window.socket.on('connect_error', () => setRealtimeIndicator('offline'));
    }
  } else {
    console.error('❌ SocketIO not available');
    setRealtimeIndicator('offline');
  }
});

