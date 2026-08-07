// Read back stored contact and assessment submissions. Never public.
//
// Both forms persist to Supabase before their notification email is attempted,
// so a mail outage leaves the submission recoverable here.
//
// Protected by a bearer token in LEADS_ADMIN_TOKEN. Without that variable the
// endpoint refuses every request rather than defaulting to open, so a missing
// configuration can never publish submitted contact details.
//
//   curl -H "Authorization: Bearer $LEADS_ADMIN_TOKEN" \
//     "https://brassops.com/api/submissions?type=contact&status=failed"
//   curl -H "Authorization: Bearer $LEADS_ADMIN_TOKEN" \
//     "https://brassops.com/api/submissions?type=assessment&format=csv" -o quiz.csv

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
const ADMIN_TOKEN = process.env.LEADS_ADMIN_TOKEN || process.env.ADMIN_API_TOKEN;

const MAX_ROWS = 10000;

const TABLES = {
  contact: {
    table: 'contact_submissions',
    csv: ['created_at', 'first_name', 'last_name', 'email', 'department', 'role', 'interest', 'message', 'status'],
  },
  assessment: {
    table: 'assessment_submissions',
    csv: ['created_at', 'first_name', 'email', 'score', 'max_score', 'tier', 'status'],
  },
};

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

// Length-independent comparison so a token cannot be probed byte by byte.
function tokensMatch(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || !a || !b) return false;
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// Spreadsheet formula injection guard, plus standard CSV quoting.
function csvCell(value) {
  let s = value == null ? '' : (typeof value === 'object' ? JSON.stringify(value) : String(value));
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  if (/[",\n\r]/.test(s)) s = `"${s.replace(/"/g, '""')}"`;
  return s;
}

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  if (!ADMIN_TOKEN) {
    console.error('Submissions read: no admin token configured, refusing');
    return res.status(503).json({ error: 'Endpoint not configured' });
  }

  const auth = req.headers.authorization || '';
  const presented = auth.startsWith('Bearer ')
    ? auth.slice(7)
    : (typeof req.query.k === 'string' ? req.query.k : '');
  if (!tokensMatch(presented, ADMIN_TOKEN)) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  if (!SUPABASE_URL || !SERVICE_KEY) {
    return res.status(503).json({ error: 'Storage not configured' });
  }

  const type = req.query.type === 'assessment' ? 'assessment' : 'contact';
  const { table, csv } = TABLES[type];
  const statusFilter = typeof req.query.status === 'string' ? req.query.status : null;
  const limit = Math.min(MAX_ROWS, Math.max(1, Number.parseInt(req.query.limit, 10) || 500));

  try {
    let path = `${table}?select=*&order=created_at.desc&limit=${limit}`;
    if (statusFilter) path += `&status=eq.${encodeURIComponent(statusFilter)}`;
    const rows = await (await sb(path)).json();

    res.setHeader('Cache-Control', 'no-store');

    if (req.query.format === 'csv') {
      const body = [
        csv.join(','),
        ...rows.map(row => csv.map(c => csvCell(row[c])).join(',')),
      ].join('\n');
      res.setHeader('Content-Type', 'text/csv; charset=utf-8');
      res.setHeader('Content-Disposition', `attachment; filename="brassops-${type}.csv"`);
      return res.status(200).send(body + '\n');
    }

    return res.status(200).json({ type, count: rows.length, submissions: rows });
  } catch (err) {
    console.error('Submissions read failed:', err?.message);
    return res.status(500).json({ error: 'Could not read submissions' });
  }
}
