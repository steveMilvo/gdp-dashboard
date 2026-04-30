async function loadLocations() {
  const res = await fetch('locations.json', { cache: 'no-store' });
  const data = await res.json();

  document.getElementById('hero-tagline').textContent = data.tagline;
  document.getElementById('week-of').textContent = 'Week of ' + formatDate(data.week_of);
  document.getElementById('next-week').textContent = data.next_week_preview;

  const wrap = document.getElementById('locations');
  wrap.innerHTML = data.this_week.map(loc => `
    <article class="location">
      <h3>${escape(loc.name)}</h3>
      <p class="when">${escape(loc.day)} ${formatDate(loc.date)} &middot; ${escape(loc.hours)}</p>
      <p class="addr">${escape(loc.address)}</p>
      <a href="${escape(loc.map)}" target="_blank" rel="noopener">Open in Maps &rarr;</a>
    </article>
  `).join('');
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString('en-AU', { day: 'numeric', month: 'long' });
}

function escape(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

loadLocations();
