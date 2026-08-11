async function pollUnits() {
  const table = document.getElementById("unitsTable");
  if (!table) return;

  try {
    const ids = Array.from(table.querySelectorAll("tr[data-unit-id]"))
      .map((row) => row.getAttribute("data-unit-id"))
      .filter(Boolean)
      .join(",");
    const url = ids ? `/api/units?ids=${encodeURIComponent(ids)}` : "/api/units";
    const res = await fetch(url);
    if (!res.ok) return;
    const data = await res.json();
    const units = data.units || [];

    for (const u of units) {
      const row = table.querySelector(`tr[data-unit-id="${u.id}"]`);
      if (!row) continue;
      const badge = row.querySelector(".badge");
      if (badge) {
        badge.className = `badge badge--${u.status}`;
        badge.textContent = u.status;
      }

      const actionCell = row.querySelector("td:last-child");
      if (actionCell) {
        if (u.status === "available") {
          actionCell.innerHTML = `<a class="btn btn--sm btn--primary" href="/user/reserve/${u.id}">Reserve</a>`;
        } else {
          actionCell.innerHTML = `<span class="muted">—</span>`;
        }
      }
    }
  } catch (_) {}
}

document.addEventListener("DOMContentLoaded", () => {
  pollUnits();
  setInterval(pollUnits, 5000);
});

