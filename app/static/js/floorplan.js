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

// Setup SocketIO real-time updates
function setupSocketIO() {
  if (!window.socket) {
    console.error('❌ SocketIO not initialized');
    return;
  }
  
  console.log('🔌 Setting up SocketIO listeners for floorplan...');
  
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
  
  // Add click handler for unit tiles
  document.querySelectorAll('.unit-tile').forEach(tile => {
    tile.addEventListener('click', () => {
      const unitId = tile.getAttribute('data-unit-id');
      const status = tile.getAttribute('data-status');
      const code = tile.querySelector('.unit-tile__meta').textContent;
      
      console.log(`Unit ${code} (ID: ${unitId}) - Status: ${status}`);
    });
  });
  
  // Setup SocketIO real-time updates
  if (window.socket) {
    // Wait for socket to connect
    if (window.socket.connected) {
      setupSocketIO();
    } else {
      window.socket.on('connect', setupSocketIO);
    }
  } else {
    console.error('❌ SocketIO not available');
  }
});

