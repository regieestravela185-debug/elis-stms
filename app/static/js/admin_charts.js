document.addEventListener("DOMContentLoaded", () => {
  // Unit Occupancy Chart
  const occupancyCtx = document.getElementById("occupancyChart");
  if (occupancyCtx) {
    const totalUnits = parseInt(document.getElementById("m_total")?.textContent || "0");
    const available = parseInt(document.getElementById("m_available")?.textContent || "0");
    const occupied = parseInt(document.getElementById("m_occupied")?.textContent || "0");
    const reserved = parseInt(document.getElementById("m_reserved")?.textContent || "0");
    const unpaid = totalUnits - available - occupied - reserved;

    new Chart(occupancyCtx, {
      type: "doughnut",
      data: {
        labels: ["Available", "Occupied", "Reserved", "Unpaid"],
        datasets: [{
          data: [available, occupied, reserved, unpaid],
          backgroundColor: [
            "rgba(34, 197, 94, 0.8)",
            "rgba(59, 130, 246, 0.8)",
            "rgba(234, 179, 8, 0.8)",
            "rgba(239, 68, 68, 0.8)"
          ],
          borderColor: [
            "rgba(34, 197, 94, 1)",
            "rgba(59, 130, 246, 1)",
            "rgba(234, 179, 8, 1)",
            "rgba(239, 68, 68, 1)"
          ],
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              padding: 20,
              usePointStyle: true
            }
          }
        },
        animation: {
          animateRotate: true,
          animateScale: true
        }
      }
    });
  }

  // Reservations by Status Chart
  const reservationCtx = document.getElementById("reservationChart");
  if (reservationCtx) {
    const pending = parseInt(document.getElementById("data_res_pending")?.value || "0");
    const approved = parseInt(document.getElementById("data_res_approved")?.value || "0");
    const rejected = parseInt(document.getElementById("data_res_rejected")?.value || "0");
    const cancelled = parseInt(document.getElementById("data_res_cancelled")?.value || "0");

    new Chart(reservationCtx, {
      type: "bar",
      data: {
        labels: ["Pending", "Approved", "Rejected", "Cancelled"],
        datasets: [{
          label: "Reservations",
          data: [pending, approved, rejected, cancelled],
          backgroundColor: [
            "rgba(234, 179, 8, 0.8)",
            "rgba(34, 197, 94, 0.8)",
            "rgba(239, 68, 68, 0.8)",
            "rgba(156, 163, 175, 0.8)"
          ],
          borderColor: [
            "rgba(234, 179, 8, 1)",
            "rgba(34, 197, 94, 1)",
            "rgba(239, 68, 68, 1)",
            "rgba(156, 163, 175, 1)"
          ],
          borderWidth: 2,
          borderRadius: 8
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              stepSize: 1
            }
          }
        },
        animation: {
          duration: 1000,
          easing: "easeInOutQuart"
        }
      }
    });
  }

  // NEW: Revenue Trend Chart
  const revenueTrendCtx = document.getElementById("revenueTrendChart");
  if (revenueTrendCtx) {
    // Get revenue data from JSON script tag
    const dataElement = document.getElementById("revenue-trend-data");
    const revenueTrendData = dataElement ? JSON.parse(dataElement.textContent) : [];
    
    const labels = revenueTrendData.map(item => item.month);
    const data = revenueTrendData.map(item => item.revenue);

    new Chart(revenueTrendCtx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [{
          label: "Revenue (PHP)",
          data: data,
          backgroundColor: "rgba(215, 179, 91, 0.1)",
          borderColor: "rgba(215, 179, 91, 1)",
          borderWidth: 3,
          fill: true,
          tension: 0.4,
          pointRadius: 6,
          pointHoverRadius: 8,
          pointBackgroundColor: "rgba(215, 179, 91, 1)",
          pointBorderColor: "#fff",
          pointBorderWidth: 2,
          pointHoverBackgroundColor: "rgba(215, 179, 91, 1)",
          pointHoverBorderColor: "#fff",
          pointHoverBorderWidth: 3
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            backgroundColor: "rgba(20, 20, 23, 0.95)",
            padding: 12,
            titleFont: {
              size: 14,
              weight: "bold"
            },
            bodyFont: {
              size: 13
            },
            callbacks: {
              label: function(context) {
                return "₱" + context.parsed.y.toLocaleString('en-US', {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2
                });
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: function(value) {
                return "₱" + value.toLocaleString('en-US');
              }
            },
            grid: {
              color: "rgba(20, 20, 23, 0.08)"
            }
          },
          x: {
            grid: {
              display: false
            }
          }
        },
        animation: {
          duration: 1500,
          easing: "easeInOutQuart"
        },
        interaction: {
          intersect: false,
          mode: "index"
        }
      }
    });
  }

  // Building Occupancy Chart
  const buildingCtx = document.getElementById("buildingOccupancyChart");
  if (buildingCtx) {
    const dataElement = document.getElementById("building-occupancy-data");
    const buildingData = dataElement ? JSON.parse(dataElement.textContent) : [];

    const labels = buildingData.map(b => b.code);
    const occupiedData = buildingData.map(b => b.occupied);
    const availableData = buildingData.map(b => b.total - b.occupied);

    new Chart(buildingCtx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Occupied",
            data: occupiedData,
            backgroundColor: "rgba(59, 130, 246, 0.8)",
            borderColor: "rgba(59, 130, 246, 1)",
            borderWidth: 2,
            borderRadius: 6,
            stack: "stack0"
          },
          {
            label: "Available",
            data: availableData,
            backgroundColor: "rgba(34, 197, 94, 0.6)",
            borderColor: "rgba(34, 197, 94, 1)",
            borderWidth: 2,
            borderRadius: 6,
            stack: "stack0"
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { padding: 16, usePointStyle: true } },
          tooltip: {
            callbacks: {
              footer: function(items) {
                const idx = items[0].dataIndex;
                const b = buildingData[idx];
                return `Occupancy rate: ${b.rate}%`;
              }
            }
          }
        },
        scales: {
          x: { stacked: true, grid: { display: false } },
          y: { stacked: true, beginAtZero: true, ticks: { stepSize: 1 } }
        },
        animation: { duration: 1200, easing: "easeInOutQuart" }
      }
    });
  }

  // Animate numbers on scroll
  const animateValue = (element, start, end, duration) => {
    let startTimestamp = null;
    const step = (timestamp) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      const value = Math.floor(progress * (end - start) + start);
      element.textContent = value.toLocaleString();
      if (progress < 1) {
        window.requestAnimationFrame(step);
      }
    };
    window.requestAnimationFrame(step);
  };

  // Animate metric numbers
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const metricNum = entry.target.querySelector('.metric__num');
        if (metricNum && !metricNum.dataset.animated) {
          const text = metricNum.textContent.replace(/[^0-9]/g, '');
          const endValue = parseInt(text) || 0;
          if (endValue > 0 && endValue < 10000) {
            metricNum.dataset.animated = 'true';
            animateValue(metricNum, 0, endValue, 1000);
          }
        }
      }
    });
  }, { threshold: 0.5 });

  document.querySelectorAll('.metric').forEach(metric => {
    observer.observe(metric);
  });
});
