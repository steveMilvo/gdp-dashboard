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
loadSocials();

const SOCIAL_ICONS = {
  instagram: { label: 'Instagram', svg: '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path fill="currentColor" d="M12 2.2c3.2 0 3.6 0 4.8.1 1.2.1 1.8.2 2.2.4.6.2 1 .5 1.5 1s.8.9 1 1.5c.2.4.4 1 .4 2.2.1 1.2.1 1.6.1 4.8s0 3.6-.1 4.8c-.1 1.2-.2 1.8-.4 2.2-.2.6-.5 1-1 1.5s-.9.8-1.5 1c-.4.2-1 .4-2.2.4-1.2.1-1.6.1-4.8.1s-3.6 0-4.8-.1c-1.2-.1-1.8-.2-2.2-.4-.6-.2-1-.5-1.5-1s-.8-.9-1-1.5c-.2-.4-.4-1-.4-2.2C2.2 15.6 2.2 15.2 2.2 12s0-3.6.1-4.8c.1-1.2.2-1.8.4-2.2.2-.6.5-1 1-1.5s.9-.8 1.5-1c.4-.2 1-.4 2.2-.4C8.4 2.2 8.8 2.2 12 2.2zm0 1.8c-3.1 0-3.5 0-4.7.1-1.1.1-1.7.2-2.1.4-.5.2-.9.4-1.2.8-.4.4-.6.7-.8 1.2-.2.4-.3 1-.4 2.1-.1 1.2-.1 1.6-.1 4.7s0 3.5.1 4.7c.1 1.1.2 1.7.4 2.1.2.5.4.9.8 1.2.4.4.7.6 1.2.8.4.2 1 .3 2.1.4 1.2.1 1.6.1 4.7.1s3.5 0 4.7-.1c1.1-.1 1.7-.2 2.1-.4.5-.2.9-.4 1.2-.8.4-.4.6-.7.8-1.2.2-.4.3-1 .4-2.1.1-1.2.1-1.6.1-4.7s0-3.5-.1-4.7c-.1-1.1-.2-1.7-.4-2.1-.2-.5-.4-.9-.8-1.2-.4-.4-.7-.6-1.2-.8-.4-.2-1-.3-2.1-.4C15.5 4 15.1 4 12 4zm0 3.1a4.9 4.9 0 1 1 0 9.8 4.9 4.9 0 0 1 0-9.8zm0 1.8a3.1 3.1 0 1 0 0 6.2 3.1 3.1 0 0 0 0-6.2zm5.1-2.2a1.15 1.15 0 1 1 0 2.3 1.15 1.15 0 0 1 0-2.3z"/></svg>' },
  facebook: { label: 'Facebook', svg: '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path fill="currentColor" d="M22 12a10 10 0 1 0-11.6 9.9v-7H7.9V12h2.5V9.8c0-2.5 1.5-3.8 3.7-3.8 1.1 0 2.2.2 2.2.2v2.4h-1.2c-1.2 0-1.6.8-1.6 1.6V12h2.7l-.4 2.9h-2.3v7A10 10 0 0 0 22 12z"/></svg>' },
  tiktok: { label: 'TikTok', svg: '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path fill="currentColor" d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-5.2 1.74 2.89 2.89 0 0 1 2.31-4.64 2.93 2.93 0 0 1 .88.13V9.4a6.84 6.84 0 0 0-1-.05A6.33 6.33 0 0 0 5.8 20.1a6.34 6.34 0 0 0 10.86-4.43V8.66a8.16 8.16 0 0 0 4.77 1.52v-3.4a4.85 4.85 0 0 1-1.84-.09z"/></svg>' },
  youtube: { label: 'YouTube', svg: '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path fill="currentColor" d="M23.5 6.5a3 3 0 0 0-2.1-2.1C19.5 4 12 4 12 4s-7.5 0-9.4.4A3 3 0 0 0 .5 6.5 31 31 0 0 0 0 12a31 31 0 0 0 .5 5.5 3 3 0 0 0 2.1 2.1c1.9.4 9.4.4 9.4.4s7.5 0 9.4-.4a3 3 0 0 0 2.1-2.1A31 31 0 0 0 24 12a31 31 0 0 0-.5-5.5zM9.6 15.6V8.4l6.2 3.6z"/></svg>' },
  twitter: { label: 'X', svg: '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path fill="currentColor" d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>' }
};

async function loadSocials() {
  try {
    const res = await fetch('/socials.json', { cache: 'no-store' });
    if (!res.ok) return;
    const data = await res.json();
    const main = document.getElementById('socials-main');
    const foot = document.getElementById('socials-foot');
    const or = document.getElementById('signup-or');

    const items = Object.entries(data)
      .filter(([k, v]) => v && SOCIAL_ICONS[k])
      .map(([k, v]) => {
        const i = SOCIAL_ICONS[k];
        return {
          key: k,
          url: v,
          mainHtml: `<li><a href="${esc(v)}" target="_blank" rel="noopener" aria-label="ManDorons on ${i.label}">${i.svg}<span>${i.label}</span></a></li>`,
          footHtml: `<li><a href="${esc(v)}" target="_blank" rel="noopener" aria-label="${i.label}">${i.svg}</a></li>`
        };
      });

    if (main) main.innerHTML = items.map(x => x.mainHtml).join('');
    if (foot) foot.innerHTML = items.map(x => x.footHtml).join('');
    if (or) or.hidden = items.length === 0;
  } catch (err) {
    /* silent — page still works without socials */
  }
}

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
