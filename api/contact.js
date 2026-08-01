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
// Submissions are persisted BEFORE the email send is attempted, so a
// provider outage can never lose a lead. In April a sender-domain
// misconfiguration silently discarded every submission; storing first makes
// that class of failure recoverable.
//
// Talks to the Vercel KV (Upstash) REST API over plain fetch so the project
// needs no npm dependency and no package.json, which would change how Vercel
// builds this otherwise-static site.
//
// Storage is strictly best-effort: if KV is unconfigured or erroring, the
// form still sends. Persistence must never be the reason a lead is lost.

const KV_URL = process.env.KV_REST_API_URL;
const KV_TOKEN = process.env.KV_REST_API_TOKEN;
const RETENTION_DAYS = Number(process.env.SUBMISSION_RETENTION_DAYS || 90);

function kvConfigured() {
  return Boolean(KV_URL && KV_TOKEN);
}

async function kvPipeline(commands) {
  const response = await fetch(`${KV_URL}/pipeline`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${KV_TOKEN}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(commands),
  });
  if (!response.ok) {
    throw new Error(`KV responded ${response.status}`);
  }
  return response.json();
}

async function storeSubmission(record) {
  if (!kvConfigured()) {
    console.warn('KV not configured; submission not persisted');
    return null;
  }
  try {
    const id = `contact:${Date.now()}:${Math.random().toString(36).slice(2, 10)}`;
    const ttlSeconds = Math.max(1, RETENTION_DAYS) * 86400;
    await kvPipeline([
      ['SET', id, JSON.stringify(record), 'EX', String(ttlSeconds)],
      ['LPUSH', 'contact:index', id],
      ['LTRIM', 'contact:index', '0', '4999'],
    ]);
    return id;
  } catch (err) {
    console.error('Failed to persist submission:', err?.message);
    return null;
  }
}

async function markSubmission(id, status, detail) {
  if (!id || !kvConfigured()) return;
  try {
    const read = await kvPipeline([['GET', id]]);
    const raw = read?.[0]?.result;
    if (!raw) return;
    const ttlSeconds = Math.max(1, RETENTION_DAYS) * 86400;
    const updated = {
      ...JSON.parse(raw),
      status,
      detail: detail ?? null,
      updatedAt: new Date().toISOString(),
    };
    await kvPipeline([
      ['SET', id, JSON.stringify(updated), 'EX', String(ttlSeconds)],
    ]);
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
    type: 'contact',
    status: 'pending',
    receivedAt: new Date().toISOString(),
    firstName,
    lastName,
    email,
    department: department || null,
    role: role || null,
    interest: interest || null,
    message: message || null,
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

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
