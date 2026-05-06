const express = require('express');
const session = require('express-session');
const nodemailer = require('nodemailer');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = parseInt(process.env.PORT || '80', 10);
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || '';
const SESSION_SECRET = process.env.SESSION_SECRET || 'dev-secret-change-me';

const ROOT = __dirname;
const DATA_DIR = path.join(ROOT, 'data');
const LOCATIONS_FILE = path.join(ROOT, 'locations.json');
const SUBSCRIBERS_FILE = path.join(DATA_DIR, 'subscribers.json');
const SOCIALS_FILE = path.join(DATA_DIR, 'socials.json');
const SOCIALS_DEFAULT = path.join(DATA_DIR, 'socials.default.json');

const SOCIAL_PLATFORMS = ['instagram', 'facebook', 'tiktok', 'youtube', 'twitter'];

fs.mkdirSync(DATA_DIR, { recursive: true });
if (!fs.existsSync(SUBSCRIBERS_FILE)) {
  fs.writeFileSync(SUBSCRIBERS_FILE, JSON.stringify({ subscribers: [] }, null, 2));
}
if (!fs.existsSync(SOCIALS_FILE)) {
  const seed = fs.existsSync(SOCIALS_DEFAULT)
    ? fs.readFileSync(SOCIALS_DEFAULT, 'utf8')
    : JSON.stringify(Object.fromEntries(SOCIAL_PLATFORMS.map(p => [p, ''])), null, 2);
  fs.writeFileSync(SOCIALS_FILE, seed);
}

function readJson(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); }
  catch { return fallback; }
}
function writeJson(file, data) {
  fs.writeFileSync(file, JSON.stringify(data, null, 2));
}
function isValidEmail(s) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(s);
}

app.set('view engine', 'ejs');
app.set('views', path.join(ROOT, 'views'));
app.use(express.json());
app.use(express.urlencoded({ extended: false }));

app.set('trust proxy', 1);
app.use(session({
  secret: SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    maxAge: 1000 * 60 * 60 * 8
  }
}));

function requireAdmin(req, res, next) {
  if (req.session && req.session.isAdmin) return next();
  return res.redirect('/admin/login');
}

app.post('/api/subscribe', (req, res) => {
  const email = String(req.body.email || '').trim().toLowerCase();
  if (!isValidEmail(email)) {
    return res.status(400).json({ ok: false, error: 'Please enter a valid email.' });
  }
  const data = readJson(SUBSCRIBERS_FILE, { subscribers: [] });
  if (data.subscribers.find(s => s.email === email)) {
    return res.json({ ok: true, message: "You're already on the list." });
  }
  data.subscribers.push({ email, subscribed_at: new Date().toISOString() });
  writeJson(SUBSCRIBERS_FILE, data);
  res.json({ ok: true, message: "Thanks! Watch your inbox each Monday." });
});

app.get('/admin/login', (req, res) => {
  if (req.session.isAdmin) return res.redirect('/admin');
  res.render('login', { error: null, configured: ADMIN_PASSWORD.length > 0 });
});

app.post('/admin/login', (req, res) => {
  if (!ADMIN_PASSWORD) {
    return res.render('login', { error: 'ADMIN_PASSWORD env var is not set on the server.', configured: false });
  }
  if (String(req.body.password) === ADMIN_PASSWORD) {
    req.session.isAdmin = true;
    return res.redirect('/admin');
  }
  res.render('login', { error: 'Wrong password.', configured: true });
});

app.get('/admin/logout', (req, res) => {
  req.session.destroy(() => res.redirect('/'));
});

app.get('/admin', requireAdmin, (req, res) => {
  const locations = readJson(LOCATIONS_FILE, { this_week: [] });
  const subs = readJson(SUBSCRIBERS_FILE, { subscribers: [] });
  const socials = readJson(SOCIALS_FILE, {});
  res.render('admin', {
    locations,
    subscribers: subs.subscribers || [],
    socials,
    platforms: SOCIAL_PLATFORMS,
    flash: req.query,
    smtpConfigured: Boolean(process.env.SMTP_HOST && process.env.SMTP_USER)
  });
});

app.post('/admin/locations', requireAdmin, (req, res) => {
  const b = req.body;
  const updated = {
    week_of: b.week_of || '',
    tagline: b.tagline || '',
    variety_now: b.variety_now || '',
    this_week: [],
    next_week_preview: b.next_week_preview || ''
  };
  for (let i = 0; i < 10; i++) {
    const name = (b[`name_${i}`] || '').trim();
    if (!name) continue;
    updated.this_week.push({
      name,
      address: (b[`address_${i}`] || '').trim(),
      day: (b[`day_${i}`] || '').trim(),
      date: (b[`date_${i}`] || '').trim(),
      hours: (b[`hours_${i}`] || '').trim()
    });
  }
  writeJson(LOCATIONS_FILE, updated);
  res.redirect('/admin?saved=1');
});

app.post('/admin/subscribers/delete', requireAdmin, (req, res) => {
  const email = String(req.body.email || '').toLowerCase();
  const data = readJson(SUBSCRIBERS_FILE, { subscribers: [] });
  data.subscribers = data.subscribers.filter(s => s.email !== email);
  writeJson(SUBSCRIBERS_FILE, data);
  res.redirect('/admin?removed=1');
});

app.post('/admin/socials', requireAdmin, (req, res) => {
  const out = {};
  for (const p of SOCIAL_PLATFORMS) {
    let v = String(req.body[p] || '').trim();
    if (v && !/^https?:\/\//i.test(v)) v = 'https://' + v;
    out[p] = v;
  }
  writeJson(SOCIALS_FILE, out);
  res.redirect('/admin?saved=socials');
});

app.get('/socials.json', (req, res) => {
  res.set('Cache-Control', 'no-store');
  res.type('application/json');
  res.sendFile(SOCIALS_FILE);
});

app.post('/admin/send-email', requireAdmin, async (req, res) => {
  const subject = (req.body.subject || '').trim();
  const body = req.body.body || '';
  if (!subject || !body) return res.redirect('/admin?error=missing');

  if (!process.env.SMTP_HOST || !process.env.SMTP_USER) {
    return res.redirect('/admin?error=smtp');
  }

  const transporter = nodemailer.createTransport({
    host: process.env.SMTP_HOST,
    port: parseInt(process.env.SMTP_PORT || '587', 10),
    secure: process.env.SMTP_SECURE === 'true',
    auth: { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS }
  });

  const fromAddr = process.env.SMTP_FROM || process.env.SMTP_USER;
  const subs = readJson(SUBSCRIBERS_FILE, { subscribers: [] });

  let sent = 0;
  let failed = 0;
  for (const sub of subs.subscribers) {
    try {
      await transporter.sendMail({
        from: `"ManDorons" <${fromAddr}>`,
        to: sub.email,
        subject,
        html: body
      });
      sent++;
    } catch (err) {
      failed++;
      console.error('Email failed for', sub.email, err.message);
    }
  }
  res.redirect(`/admin?sent=${sent}&failed=${failed}`);
});

app.get('/locations.json', (req, res) => {
  res.set('Cache-Control', 'no-store');
  res.type('application/json');
  res.sendFile(LOCATIONS_FILE);
});

// Staff portal — serve without redirect (no port leakage)
app.get(['/staff', '/staff.html'], (req, res) => {
  res.set('Cache-Control', 'no-store');
  res.sendFile(path.join(ROOT, 'staff.html'));
});

// Staff dashboard — multiple clean URLs
app.get(['/staff-dashboard', '/staff-dashboard.html', '/dashboard'], (req, res) => {
  res.set('Cache-Control', 'no-store');
  res.sendFile(path.join(ROOT, 'staff-dashboard.html'));
});

app.use(express.static(ROOT, {
  index: 'index.html',
  setHeaders(res, filePath) {
    if (/\.(jpg|jpeg|png|gif|webp|svg|woff2)$/i.test(filePath)) {
      res.set('Cache-Control', 'public, max-age=2592000');
    }
  }
}));

app.listen(PORT, () => {
  console.log(`ManDorons listening on :${PORT}`);
});
