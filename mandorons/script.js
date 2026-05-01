async function loadLocations() {
  const res = await fetch('locations.json', { cache: 'no-store' });
  const data = await res.json();

  if (data.tagline) {
    document.getElementById('hero-tagline').textContent = data.tagline;
  }
  document.getElementById('week-of').textContent = 'Week of ' + formatDate(data.week_of);
  document.getElementById('next-week').textContent = data.next_week_preview;

  const wrap = document.getElementById('locations');
  wrap.innerHTML = data.this_week.map(loc => `
    <article class="location">
      <h3>${esc(loc.name)}</h3>
      <p class="when">${esc(loc.day)} ${formatDate(loc.date)} &middot; ${esc(loc.hours)}</p>
      <p class="addr">${esc(loc.address)}</p>
    </article>
  `).join('');
}

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('en-AU', { day: 'numeric', month: 'long' });
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

loadLocations();
