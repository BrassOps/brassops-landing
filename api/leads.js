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

const KV_URL = process.env.KV_REST_API_URL;
const KV_TOKEN = process.env.KV_REST_API_TOKEN;
const ADMIN_TOKEN = process.env.LEADS_ADMIN_TOKEN;
const BOOTH_TOKEN = process.env.BOOTH_TOKEN;

const MAX_FETCH = 5000;

async function kv(commands) {
  const r = await fetch(`${KV_URL}/pipeline`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${KV_TOKEN}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(commands),
  });
  if (!r.ok) throw new Error(`KV responded ${r.status}`);
  return r.json();
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

// Spreadsheet formula injection guard, and standard CSV quoting.
function csvCell(value) {
  let s = String(value ?? '');
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  if (/[",\n\r]/.test(s)) s = `"${s.replace(/"/g, '""')}"`;
  return s;
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

  if (!KV_URL || !KV_TOKEN) {
    return res.status(503).json({ error: 'Storage not configured' });
  }

  const wantsCsv = req.query.format === 'csv';
  if (wantsCsv && !isAdmin) {
    return res.status(403).json({ error: 'Export requires the admin token' });
  }

  try {
    const idxRes = await kv([['LRANGE', 'leads:index', '0', String(MAX_FETCH - 1)]]);
    const ids = idxRes?.[0]?.result ?? [];

    let leads = [];
    if (ids.length) {
      const recs = await kv(ids.map(id => ['GET', id]));
      leads = recs
        .map(r => {
          if (!r?.result) return null;
          try { return JSON.parse(r.result); } catch (_) { return null; }
        })
        .filter(Boolean);
    }

    // Newest first. The index is LPUSHed so it is already in that order, but
    // sorting explicitly keeps it correct if the index is ever rebuilt.
    leads.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));

    if (wantsCsv) {
      const header = 'created_at,name,email,agency,role,temperature,notes,source';
      const rows = leads.map(l =>
        [l.created_at, l.name, l.email, l.agency, l.role, l.temperature, l.notes, l.source]
          .map(csvCell)
          .join(',')
      );
      res.setHeader('Content-Type', 'text/csv; charset=utf-8');
      res.setHeader('Content-Disposition', 'attachment; filename="brassops-leads.csv"');
      res.setHeader('Cache-Control', 'no-store');
      return res.status(200).send([header, ...rows].join('\n') + '\n');
    }

    const todayKey = new Date().toISOString().slice(0, 10);
    const todays = leads.filter(l => String(l.created_at).slice(0, 10) === todayKey);

    res.setHeader('Cache-Control', 'no-store');

    // The booth token sees counts and today's captures only. Full history is
    // reserved for the admin token.
    return res.status(200).json({
      total: leads.length,
      today: todays.length,
      leads: isAdmin && req.query.scope === 'all' ? leads : todays,
    });
  } catch (err) {
    console.error('Leads read failed:', err?.message);
    return res.status(500).json({ error: 'Could not read leads' });
  }
}
