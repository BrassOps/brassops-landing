// Allowed origins for cross-site submission protection
const ALLOWED_ORIGINS = [
  'https://brassops.com',
  'https://www.brassops.com',
];

// Input length limits
const LIMITS = {
  firstName: 100,
  lastName: 100,
  email: 255,
  department: 200,
  role: 100,
  interest: 100,
  message: 5000,
};

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// ── Submission storage ───────────────────────────────────────────────────
// Submissions are persisted BEFORE the email send is attempted, so a provider
// outage can never lose one. In April a sender domain misconfiguration
// silently discarded every submission; storing first makes that class of
// failure recoverable.
//
// Talks to Supabase PostgREST over plain fetch so the project needs no npm
// dependency and no package.json, which would change how Vercel builds this
// otherwise static site.
//
// Storage here is deliberately best effort, unlike api/lead.js. The contact
// form has two independent channels, the database and the notification email,
// so a storage outage must not stop the message reaching the inbox.

// The Vercel Supabase integration and a hand created project expose these
// under different names. Accept the common variants.
const SUPABASE_URL = (
  process.env.SUPABASE_URL ||
  process.env.NEXT_PUBLIC_SUPABASE_URL ||
  process.env.POSTGRES_SUPABASE_URL ||
  ''
).replace(/\/+$/, '');
const SERVICE_KEY =
  process.env.SUPABASE_SERVICE_ROLE_KEY ||
  process.env.SUPABASE_SERVICE_KEY ||
  process.env.POSTGRES_SUPABASE_SERVICE_ROLE_KEY;

const STORE_TABLE = 'contact_submissions';

function storageConfigured() {
  return Boolean(SUPABASE_URL && SERVICE_KEY);
}

async function sb(path, init = {}) {
  const r = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    ...init,
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      'Content-Type': 'application/json',
      ...(init.headers || {}),
    },
  });
  if (!r.ok) {
    const detail = await r.text().catch(() => '');
    throw new Error(`Supabase ${r.status}: ${detail.slice(0, 200)}`);
  }
  return r;
}

async function storeSubmission(record) {
  if (!storageConfigured()) {
    console.warn('Supabase not configured; submission not persisted');
    return null;
  }
  try {
    const r = await sb(STORE_TABLE, {
      method: 'POST',
      headers: { Prefer: 'return=representation' },
      body: JSON.stringify(record),
    });
    const rows = await r.json();
    return (Array.isArray(rows) ? rows[0] : rows)?.id ?? null;
  } catch (err) {
    console.error('Failed to persist submission:', err?.message);
    return null;
  }
}

async function markSubmission(id, status, detail) {
  if (id == null || !storageConfigured()) return;
  try {
    await sb(`${STORE_TABLE}?id=eq.${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({
        status,
        detail: detail == null ? null : (typeof detail === 'string' ? detail : JSON.stringify(detail)),
      }),
    });
  } catch (err) {
    console.error('Failed to update submission status:', err?.message);
  }
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Origin check — prevent cross-site submissions
  const origin = req.headers.origin || req.headers.referer || '';
  const isAllowedOrigin =
    ALLOWED_ORIGINS.some(a => origin.startsWith(a)) ||
    origin.startsWith('http://localhost');
  if (origin && !isAllowedOrigin) {
    return res.status(403).json({ error: 'Forbidden' });
  }

  // Body validation
  if (!req.body || typeof req.body !== 'object') {
    return res.status(400).json({ error: 'Invalid request body' });
  }

  const { firstName, lastName, email, department, role, interest, message, website } = req.body;

  // Honeypot — if the hidden "website" field is filled, silently pretend success
  if (website) {
    return res.status(200).json({ success: true });
  }

  // Required field validation
  if (!firstName || !lastName || !email) {
    return res.status(400).json({ error: 'Missing required fields' });
  }

  // Type validation
  if (typeof firstName !== 'string' || typeof lastName !== 'string' || typeof email !== 'string') {
    return res.status(400).json({ error: 'Invalid field types' });
  }

  // Length validation
  if (
    firstName.length > LIMITS.firstName ||
    lastName.length > LIMITS.lastName ||
    email.length > LIMITS.email ||
    (department && String(department).length > LIMITS.department) ||
    (role && String(role).length > LIMITS.role) ||
    (interest && String(interest).length > LIMITS.interest) ||
    (message && String(message).length > LIMITS.message)
  ) {
    return res.status(400).json({ error: 'Input exceeds maximum length' });
  }

  // Email format validation
  if (!EMAIL_REGEX.test(email)) {
    return res.status(400).json({ error: 'Invalid email format' });
  }

  // Persist before any send is attempted, and before the API key check, so
  // even a server misconfiguration leaves the lead recoverable.
  const submissionId = await storeSubmission({
    status: 'pending',
    first_name: firstName,
    last_name: lastName,
    email,
    department: department || null,
    role: role || null,
    interest: interest || null,
    message: message || null,
    ip: clientIp(req),
    user_agent: String(req.headers['user-agent'] || '').slice(0, 400) || null,
  });

  const apiKey = process.env.SMTP2GO_API_KEY;
  if (!apiKey) {
    console.error('SMTP2GO_API_KEY not configured');
    await markSubmission(submissionId, 'failed', 'SMTP2GO_API_KEY not configured');
    return res.status(500).json({ error: 'Server configuration error' });
  }

  const recipient = process.env.CONTACT_RECIPIENT || 'info@brassops.com';

  const htmlBody = `
    <h2>New Contact Form Submission</h2>
    <table style="border-collapse:collapse;width:100%;max-width:600px;font-family:sans-serif;">
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Name</td><td style="padding:8px 12px;border-bottom:1px solid #eee;">${escapeHtml(firstName)} ${escapeHtml(lastName)}</td></tr>
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Email</td><td style="padding:8px 12px;border-bottom:1px solid #eee;">${escapeHtml(email)}</td></tr>
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Department</td><td style="padding:8px 12px;border-bottom:1px solid #eee;">${escapeHtml(department || 'Not provided')}</td></tr>
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Role</td><td style="padding:8px 12px;border-bottom:1px solid #eee;">${escapeHtml(role || 'Not selected')}</td></tr>
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Interest</td><td style="padding:8px 12px;border-bottom:1px solid #eee;">${escapeHtml(interest || 'Not selected')}</td></tr>
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;vertical-align:top;">Message</td><td style="padding:8px 12px;">${escapeHtml(message || 'No message provided').replace(/\n/g, '<br>')}</td></tr>
    </table>
  `;

  const textBody = [
    `Name: ${firstName} ${lastName}`,
    `Email: ${email}`,
    `Department: ${department || 'Not provided'}`,
    `Role: ${role || 'Not selected'}`,
    `Interest: ${interest || 'Not selected'}`,
    `Message: ${message || 'No message provided'}`,
  ].join('\n');

  // Sanitize subject line — strip newlines to prevent header injection
  const safeFirst = String(firstName).replace(/[\r\n]/g, '').slice(0, 50);
  const safeLast = String(lastName).replace(/[\r\n]/g, '').slice(0, 50);
  const safeInterest = String(interest || 'General').replace(/[\r\n]/g, '').slice(0, 50);

  try {
    const response = await fetch('https://api.smtp2go.com/v3/email/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: apiKey,
        to: [recipient],
        sender: 'BrassOps Contact Form <noreply@brassops.com>',
        subject: `New Contact: ${safeFirst} ${safeLast} (${safeInterest})`,
        html_body: htmlBody,
        text_body: textBody,
      }),
    });

    const data = await response.json();

    if (data.data?.succeeded > 0) {
      await markSubmission(submissionId, 'sent');
      return res.status(200).json({ success: true });
    }

    // Log the provider's actual reason so failures are diagnosable in Vercel
    // logs. Only provider metadata is logged, never submitted user data.
    const failureDetail = {
      httpStatus: response.status,
      errorCode: data?.data?.error_code ?? data?.error_code ?? null,
      error: data?.data?.error ?? data?.error ?? null,
      failures: data?.data?.failures ?? null,
    };
    console.error('SMTP2GO send failed', failureDetail);
    await markSubmission(submissionId, 'failed', failureDetail);
    return res.status(502).json({ error: 'Email provider rejected the message' });
  } catch (err) {
    console.error('SMTP2GO request failed:', err?.message);
    await markSubmission(submissionId, 'failed', { error: err?.message ?? 'request failed' });
    return res.status(502).json({ error: 'Could not reach email provider' });
  }
}

function clientIp(req) {
  const fwd = req.headers['x-forwarded-for'];
  if (typeof fwd === 'string' && fwd.length) return fwd.split(',')[0].trim();
  return req.headers['x-real-ip'] || 'unknown';
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
