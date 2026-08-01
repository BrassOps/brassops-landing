// Read-back endpoint for stored form submissions.
//
// Submissions are persisted by api/contact.js and api/assessment.js before any
// email send is attempted, so a provider outage leaves leads recoverable. This
// endpoint exposes them for retrieval.
//
// Protected by a bearer token held in ADMIN_API_TOKEN. Without that variable
// set the endpoint refuses every request rather than defaulting to open, so a
// missing configuration can never silently publish submitted contact details.
//
// Usage:
//   curl -H "Authorization: Bearer $ADMIN_API_TOKEN" \
//     "https://brassops.com/api/submissions?type=contact&status=failed"

const KV_URL = process.env.KV_REST_API_URL;
const KV_TOKEN = process.env.KV_REST_API_TOKEN;
const ADMIN_TOKEN = process.env.ADMIN_API_TOKEN;

const MAX_LIMIT = 500;

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

// Constant-time-ish comparison to avoid leaking token length or prefix
function tokensMatch(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Fail closed: no configured token means no access, ever.
  if (!ADMIN_TOKEN) {
    console.error('ADMIN_API_TOKEN not configured; refusing submissions read');
    return res.status(503).json({ error: 'Endpoint not configured' });
  }

  const auth = req.headers.authorization || '';
  const provided = auth.startsWith('Bearer ') ? auth.slice(7) : '';
  if (!tokensMatch(provided, ADMIN_TOKEN)) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  if (!KV_URL || !KV_TOKEN) {
    return res.status(503).json({ error: 'Storage not configured' });
  }

  const type = req.query.type === 'assessment' ? 'assessment' : 'contact';
  const statusFilter = typeof req.query.status === 'string' ? req.query.status : null;
  const limit = Math.min(
    MAX_LIMIT,
    Math.max(1, Number.parseInt(req.query.limit, 10) || 100)
  );

  try {
    const indexKey = `${type}:index`;
    const indexRead = await kvPipeline([['LRANGE', indexKey, '0', String(limit - 1)]]);
    const ids = indexRead?.[0]?.result ?? [];

    if (!ids.length) {
      return res.status(200).json({ type, count: 0, submissions: [] });
    }

    const records = await kvPipeline(ids.map(id => ['GET', id]));
    const submissions = records
      .map((entry, i) => {
        if (!entry?.result) return null;
        try {
          return { id: ids[i], ...JSON.parse(entry.result) };
        } catch (_) {
          return null;
        }
      })
      .filter(Boolean)
      .filter(s => !statusFilter || s.status === statusFilter);

    return res.status(200).json({
      type,
      count: submissions.length,
      submissions,
    });
  } catch (err) {
    console.error('Failed to read submissions:', err?.message);
    return res.status(500).json({ error: 'Could not read submissions' });
  }
}
