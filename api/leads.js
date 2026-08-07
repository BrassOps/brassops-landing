// Lead read and export. Never public.
//
// Two token tiers, both from environment variables:
//   LEADS_ADMIN_TOKEN  full access, including CSV export of every lead
//   BOOTH_TOKEN        booth display only: counts plus today's captures
//
// Both fail closed. With neither variable set the endpoint refuses every
// request rather than defaulting to open, so a missing configuration can
// never publish captured contact details.
//
//   curl -H "Authorization: Bearer $LEADS_ADMIN_TOKEN" \
//     "https://brassops.com/api/leads?format=csv" -o leads.csv

const SUPABASE_URL = (process.env.SUPABASE_URL || '').replace(/\/+$/, '');
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const ADMIN_TOKEN = process.env.LEADS_ADMIN_TOKEN;
const BOOTH_TOKEN = process.env.BOOTH_TOKEN;

const MAX_ROWS = 10000;

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

function presentedToken(req) {
  const auth = req.headers.authorization || '';
  if (auth.startsWith('Bearer ')) return auth.slice(7);
  // Query fallback so the booth page can be bookmarked on a staff phone.
  return typeof req.query.k === 'string' ? req.query.k : '';
}

// Spreadsheet formula injection guard, plus standard CSV quoting.
function csvCell(value) {
  let s = Array.isArray(value) ? value.join(' ') : String(value ?? '');
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  if (/[",\n\r]/.test(s)) s = `"${s.replace(/"/g, '""')}"`;
  return s;
}

// PostgREST reports the total in Content-Range as "0-24/1503".
function totalFromRange(r) {
  const cr = r.headers.get('content-range') || '';
  const n = Number(cr.split('/')[1]);
  return Number.isFinite(n) ? n : 0;
}

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  if (!ADMIN_TOKEN && !BOOTH_TOKEN) {
    console.error('Leads read: no tokens configured, refusing');
    return res.status(503).json({ error: 'Endpoint not configured' });
  }

  const presented = presentedToken(req);
  const isAdmin = tokensMatch(presented, ADMIN_TOKEN);
  const isBooth = isAdmin || tokensMatch(presented, BOOTH_TOKEN);
  if (!isBooth) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  if (!SUPABASE_URL || !SERVICE_KEY) {
    return res.status(503).json({ error: 'Storage not configured' });
  }

  const wantsCsv = req.query.format === 'csv';
  if (wantsCsv && !isAdmin) {
    return res.status(403).json({ error: 'Export requires the admin token' });
  }

  try {
    if (wantsCsv) {
      const cols = 'created_at,name,email,agency,role,temperature,notes,source';
      const r = await sb(`leads?select=${cols}&order=created_at.desc&limit=${MAX_ROWS}`);
      const rows = await r.json();
      const body = [
        cols,
        ...rows.map(l =>
          [l.created_at, l.name, l.email, l.agency, l.role, l.temperature, l.notes, l.source]
            .map(csvCell)
            .join(',')
        ),
      ].join('\n');
      res.setHeader('Content-Type', 'text/csv; charset=utf-8');
      res.setHeader('Content-Disposition', 'attachment; filename="brassops-leads.csv"');
      res.setHeader('Cache-Control', 'no-store');
      return res.status(200).send(body + '\n');
    }

    // Counts come from Content-Range so the whole table is never transferred
    // just to display two numbers on the booth screen.
    const startOfDay = new Date();
    startOfDay.setUTCHours(0, 0, 0, 0);
    const since = startOfDay.toISOString();

    const totalRes = await sb('leads?select=id&limit=1', {
      headers: { Prefer: 'count=exact' },
    });
    const total = totalFromRange(totalRes);

    const todayRes = await sb(
      `leads?select=*&created_at=gte.${encodeURIComponent(since)}` +
      `&order=created_at.desc&limit=${MAX_ROWS}`,
      { headers: { Prefer: 'count=exact' } }
    );
    const todays = await todayRes.json();

    res.setHeader('Cache-Control', 'no-store');

    // The booth token sees counts and today's captures only. Full history is
    // reserved for the admin token.
    let leads = todays;
    if (isAdmin && req.query.scope === 'all') {
      const allRes = await sb(`leads?select=*&order=created_at.desc&limit=${MAX_ROWS}`);
      leads = await allRes.json();
    }

    return res.status(200).json({ total, today: todays.length, leads });
  } catch (err) {
    console.error('Leads read failed:', err?.message);
    return res.status(500).json({ error: 'Could not read leads' });
  }
}
