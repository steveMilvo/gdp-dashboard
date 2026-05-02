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

const subscribeForm = document.getElementById('subscribe-form');
const subscribeMessage = document.getElementById('subscribe-message');
if (subscribeForm) {
  subscribeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = subscribeForm.querySelector('input[name="email"]');
    const button = subscribeForm.querySelector('button');
    const email = input.value.trim();
    button.disabled = true;
    const original = button.textContent;
    button.textContent = 'Subscribing…';
    subscribeMessage.textContent = '';
    subscribeMessage.className = 'signup-message';
    try {
      const res = await fetch('/api/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        subscribeMessage.textContent = data.message || 'Thanks!';
        subscribeMessage.className = 'signup-message success';
        subscribeForm.reset();
      } else {
        subscribeMessage.textContent = data.error || 'Something went wrong. Try again.';
        subscribeMessage.className = 'signup-message error';
      }
    } catch (err) {
      subscribeMessage.textContent = 'Could not connect. Try again later.';
      subscribeMessage.className = 'signup-message error';
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  });
}
