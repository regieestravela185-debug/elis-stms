let currentBuilding = null;
let currentFloor = "all";

function applyFilters() {
  // Each floor-section now belongs to exactly one building+floor (even
  // when it has zero units, rendered as an empty-state placeholder), so
  // sections are filtered directly instead of being hidden based on
  // whether they happen to contain a visible tile — a floor with
  // genuinely no units yet must still show up, not disappear.
  document.querySelectorAll(".floor-section").forEach((sec) => {
    const b = sec.getAttribute("data-building");
    const f = sec.getAttribute("data-floor");
    const buildingMatch = !currentBuilding || b === currentBuilding;
    const floorMatch = currentFloor === "all" || f === currentFloor;
    sec.style.display = buildingMatch && floorMatch ? "" : "none";
  });
}

function rebuildFloorPills(buildingId) {
  const bar = document.getElementById("floorFilterBar");
  if (!bar) return;

  // Collect unique floors for this building (from the sections
  // themselves, since every floor up to the building's limit has one).
  const floors = new Set();
  document.querySelectorAll(".floor-section").forEach((sec) => {
    if (sec.getAttribute("data-building") === buildingId) {
      floors.add(sec.getAttribute("data-floor"));
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
      const paidBadge = data.tenant && data.tenant.paid_this_month === true
        ? '<span style="display:inline-block; margin-top:8px; background:#22c55e1a; color:#22c55e; border:1px solid #22c55e40; font-weight:700; font-size:11px; padding:3px 10px; border-radius:999px;">Paid this month</span>'
        : data.tenant && data.tenant.paid_this_month === false
          ? '<span style="display:inline-block; margin-top:8px; background:#ef44441a; color:#ef4444; border:1px solid #ef444440; font-weight:700; font-size:11px; padding:3px 10px; border-radius:999px;">Unpaid this month</span>'
          : '';
      const tenantBlock = data.tenant
        ? `<div style="background:rgba(20,20,23,0.03); border-radius:12px; padding:18px; margin-top:16px;">
             <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:#64748b; margin-bottom:8px;">Current Tenant</div>
             <div style="font-size:16px; font-weight:700;">${data.tenant.name}</div>
             ${paidBadge}
             <div style="margin-top:12px; display:flex; flex-direction:column; gap:6px;">
               ${data.tenant.email ? `<div class="muted" style="font-size:13px;">${data.tenant.email}</div>` : ''}
               ${data.tenant.move_in ? `<div class="muted" style="font-size:13px;">Move-in: ${data.tenant.move_in}</div>` : ''}
               ${data.tenant.contract_end
                 ? `<div class="muted" style="font-size:13px;">Contract ends ${data.tenant.contract_end}</div>`
                 : (data.tenant.is_commercial ? '' : '<div class="muted" style="font-size:13px;">Month-to-month — no fixed end date</div>')}
             </div>
           </div>`
        : '';
      const viewProfileBtn = data.tenant
        ? `<a href="${data.tenant.user_details_url}" class="btn btn--ghost" style="flex:1; text-align:center; box-sizing:border-box;">View Tenant Profile</a>`
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
        <div style="display:flex; gap:10px; margin-top:16px;">
          ${viewProfileBtn}
          <a href="${data.edit_url}" class="btn btn--primary" style="flex:1; text-align:center; box-sizing:border-box;">Edit Unit</a>
        </div>
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

  // Type quick-jump: Residential/Commercial isn't an independent filter
  // anymore (every building is 100% one or the other), so these jump to
  // the representative building instead of a Building + Type combo that
  // could silently show zero units.
  const jumpButtons = document.querySelectorAll("#typeJumpBar .type-jump-btn");
  const jumpMessage = document.getElementById("typeJumpMessage");
  jumpButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const type = btn.getAttribute("data-jump-type");
      const matches = Array.from(document.querySelectorAll(`.building-btn[data-type="${type}"]`));
      if (!matches.length) return;
      const target = matches[0];
      const codes = matches.map((b) => b.getAttribute("data-building-label")).filter(Boolean);

      buttons.forEach((b) => b.classList.remove("is-active"));
      target.classList.add("is-active");
      filterByBuilding(target.getAttribute("data-building"));
      target.scrollIntoView({ behavior: "smooth", block: "nearest" });

      if (jumpMessage) {
        if (type === "commercial") {
          jumpMessage.textContent = `${codes[0]} is the only Commercial building — showing all its units.`;
        } else {
          jumpMessage.textContent = codes.length > 1
            ? `Buildings ${codes.join(", ")} are Residential — showing ${codes[0]}. Switch buildings in the sidebar to view the others.`
            : `${codes[0]} is the only Residential building.`;
        }
        jumpMessage.hidden = false;
      }
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

