// Trade show lead capture.
//
// Every lead is written to the hosted database (Vercel KV / Upstash) at the
// moment of submission. Nothing is kept in localStorage or on the filesystem.
//
// Unlike api/contact.js, persistence here is NOT best effort. If the write
// fails this endpoint returns an error so the page can keep the prospect's
// input on screen and offer retry plus a mailto fallback. A lead captured at a
// booth cannot be re-collected, so a silent success on a failed write would be
// the worst possible outcome.
//
// Talks to the KV REST API over plain fetch so the project needs no npm
// dependency and no package.json, which would change how Vercel builds this
// otherwise-static site.

const KV_URL = process.env.KV_REST_API_URL;
const KV_TOKEN = process.env.KV_REST_API_TOKEN;
const SMTP_KEY = process.env.SMTP2GO_API_KEY;
const NOTIFY_TO = process.env.LEAD_NOTIFY_RECIPIENT || 'brassops01@gmail.com';

const ALLOWED_ORIGINS = ['https://brassops.com', 'https://www.brassops.com'];

const LIMITS = { name: 120, email: 255, agency: 200, role: 60, notes: 500 };
const ROLES = ['Instructor', 'Rangemaster', 'Admin-Command', 'Chief-Sheriff', 'Academy-Trainer', 'Other'];
const TEMPERATURES = ['HOT', 'WARM', 'COLD'];
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Minimum time on page before a submission is considered organic.
const MIN_ELAPSED_MS = 3000;
// Per-IP ceiling and window.
const RATE_MAX = 12;
const RATE_WINDOW_S = 600;

async function kv(commands) {
  const r = await fetch(`${KV_URL}/pipeline`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${KV_TOKEN}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(commands),
  });
  if (!r.ok) throw new Error(`KV responded ${r.status}`);
  return r.json();
}

function clientIp(req) {
  const fwd = req.headers['x-forwarded-for'];
  if (typeof fwd === 'string' && fwd.length) return fwd.split(',')[0].trim();
  return req.headers['x-real-ip'] || 'unknown';
}

function str(v, max) {
  if (typeof v !== 'string') return '';
  return v.trim().slice(0, max);
}

function csvSafe(v) {
  // Neutralise spreadsheet formula injection on export.
  const s = String(v ?? '');
  return /^[=+\-@\t\r]/.test(s) ? `'${s}` : s;
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const origin = req.headers.origin || req.headers.referer || '';
  const originOk =
    ALLOWED_ORIGINS.some(a => origin.startsWith(a)) || origin.startsWith('http://localhost');
  if (origin && !originOk) {
    return res.status(403).json({ error: 'Forbidden' });
  }

  if (!req.body || typeof req.body !== 'object') {
    return res.status(400).json({ error: 'Invalid request body' });
  }

  const { website, elapsedMs } = req.body;

  // Honeypot. The one case the brief allows us to drop outright.
  if (website) {
    return res.status(200).json({ ok: true });
  }

  const source = req.body.source === 'staff' ? 'staff' : 'qr';
  const name = str(req.body.name, LIMITS.name);
  const email = str(req.body.email, LIMITS.email).toLowerCase();
  const agency = str(req.body.agency, LIMITS.agency);
  const roleRaw = str(req.body.role, LIMITS.role);
  const role = ROLES.includes(roleRaw) ? roleRaw : '';
  const notesRaw = str(req.body.notes, LIMITS.notes);
  const tempRaw = str(req.body.temperature, 12).toUpperCase();

  // Staff-only fields are ignored on the public form so a crafted request
  // cannot inject a temperature or note into a QR lead.
  const temperature = source === 'staff' && TEMPERATURES.includes(tempRaw) ? tempRaw : null;
  const notes = source === 'staff' && notesRaw ? notesRaw : null;

  if (!KV_URL || !KV_TOKEN) {
    console.error('Lead capture: KV not configured, refusing to accept the lead');
    return res.status(503).json({ error: 'Lead storage is not configured' });
  }

  const ip = clientIp(req);
  const flags = [];

  // Validation problems are recorded rather than discarded. The caller still
  // gets a 400 so the person can correct the field, but a half-captured lead
  // is kept and flagged: someone who mistypes their email at a booth cannot be
  // chased down again afterwards.
  let validationError = null;
  if (source === 'staff') {
    if (!name && !email) validationError = 'Enter a name or an email';
  } else if (!name || !email) {
    validationError = 'Name and email are both required';
  }
  if (!validationError && email && !EMAIL_RE.test(email)) {
    validationError = 'That email address does not look right';
  }
  if (validationError) flags.push('invalid');

  // A submission with nothing usable in it is not a lead. Storing these would
  // fill the table with empty rows from bots probing the endpoint.
  if (validationError && !name && !email) {
    return res.status(400).json({ error: validationError });
  }

  // Submitted implausibly fast. Flagged rather than dropped: a fast human is
  // far more likely at a booth than a bot, and losing a real lead is worse
  // than storing a suspicious row that can be filtered later.
  const elapsed = Number(elapsedMs);
  if (source === 'qr' && (!Number.isFinite(elapsed) || elapsed < MIN_ELAPSED_MS)) {
    flags.push('too_fast');
  }

  // Per-IP rate limit. Also flagged rather than dropped. Booth traffic can
  // legitimately share one venue NAT address.
  try {
    const key = `leadrate:${ip}`;
    const out = await kv([['INCR', key], ['EXPIRE', key, String(RATE_WINDOW_S), 'NX']]);
    const count = Number(out?.[0]?.result ?? 0);
    if (count > RATE_MAX) flags.push('rate_limited');
  } catch (err) {
    console.error('Lead capture: rate check failed:', err?.message);
  }

  const record = {
    created_at: new Date().toISOString(),
    name,
    email,
    agency,
    role,
    temperature,
    notes,
    source,
    ip,
    user_agent: str(req.headers['user-agent'], 400),
    flags,
  };

  let id;
  try {
    id = `lead:${Date.now()}:${Math.random().toString(36).slice(2, 10)}`;
    record.id = id;
    // Duplicates are stored, never rejected. A duplicate row is cheap; a lost
    // lead is not.
    await kv([
      ['SET', id, JSON.stringify(record)],
      ['LPUSH', 'leads:index', id],
    ]);
  } catch (err) {
    console.error('Lead capture: write failed:', err?.message);
    return res.status(502).json({ error: 'Could not save the lead' });
  }

  // Stored and flagged, but the caller is still told what to fix.
  if (validationError) {
    return res.status(400).json({ error: validationError });
  }

  // Notification is strictly best effort and must never fail the submission.
  if (SMTP_KEY) {
    try {
      const lines = [
        `Name: ${name || 'not given'}`,
        `Email: ${email || 'not given'}`,
        `Agency: ${agency || 'not given'}`,
        `Role: ${role || 'not given'}`,
        `Temperature: ${temperature || 'not set'}`,
        `Notes: ${notes || 'none'}`,
        `Source: ${source}`,
        `Captured: ${record.created_at}`,
        flags.length ? `Flags: ${flags.join(', ')}` : '',
      ].filter(Boolean);
      const subjName = (name || email || 'Unnamed').replace(/[\r\n]/g, '').slice(0, 60);
      await fetch('https://api.smtp2go.com/v3/email/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: SMTP_KEY,
          to: [NOTIFY_TO],
          sender: 'BrassOps Leads <noreply@brassops.com>',
          subject: `New lead (${source}): ${subjName}`,
          text_body: lines.join('\n'),
        }),
      });
    } catch (err) {
      console.error('Lead capture: notification email failed:', err?.message);
    }
  }

  return res.status(200).json({ ok: true, id });
}

export { csvSafe };
