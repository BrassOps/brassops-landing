const ALLOWED_ORIGINS = [
  'https://brassops.com',
  'https://www.brassops.com',
];

const LIMITS = {
  firstName: 100,
  email: 255,
  tier: 50,
  weakAreaTitle: 200,
  weakAreaLevel: 50,
  weakAreasMax: 20,
};

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Origin check
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

  const { firstName, email, score, maxScore, tier, weakAreas, website } = req.body;

  // Honeypot
  if (website) {
    return res.status(200).json({ success: true });
  }

  // Required fields
  if (!firstName || !email) {
    return res.status(400).json({ error: 'Missing required fields' });
  }

  // Type validation
  if (typeof firstName !== 'string' || typeof email !== 'string') {
    return res.status(400).json({ error: 'Invalid field types' });
  }

  // Length validation
  if (firstName.length > LIMITS.firstName || email.length > LIMITS.email) {
    return res.status(400).json({ error: 'Input exceeds maximum length' });
  }

  // Email format validation
  if (!EMAIL_REGEX.test(email)) {
    return res.status(400).json({ error: 'Invalid email format' });
  }

  // Score validation
  const scoreNum = Number(score);
  const maxScoreNum = Number(maxScore);
  if (!Number.isFinite(scoreNum) || scoreNum < 0 || scoreNum > 1000) {
    return res.status(400).json({ error: 'Invalid score' });
  }
  if (!Number.isFinite(maxScoreNum) || maxScoreNum < 0 || maxScoreNum > 1000) {
    return res.status(400).json({ error: 'Invalid maxScore' });
  }

  // Tier validation
  const safeTier = tier && typeof tier === 'string' && tier.length <= LIMITS.tier
    ? tier
    : 'Unknown';

  // WeakAreas validation
  const safeWeakAreas = Array.isArray(weakAreas)
    ? weakAreas.slice(0, LIMITS.weakAreasMax).filter(w =>
        w && typeof w === 'object' &&
        typeof w.level === 'string' && w.level.length <= LIMITS.weakAreaLevel &&
        typeof w.title === 'string' && w.title.length <= LIMITS.weakAreaTitle
      )
    : [];

  const smtpKey = process.env.SMTP2GO_API_KEY;
  const brevoKey = process.env.BREVO_API_KEY;

  if (!smtpKey) {
    console.error('SMTP2GO_API_KEY not configured');
    return res.status(500).json({ error: 'Server configuration error' });
  }

  const recipient = process.env.CONTACT_RECIPIENT || 'brassops01@gmail.com';

  // Build email content
  const weakList = safeWeakAreas.map(w =>
    `<tr><td style="padding:6px 12px;border-bottom:1px solid #eee;color:#b03020;font-weight:600;">${escapeHtml(w.level)}</td><td style="padding:6px 12px;border-bottom:1px solid #eee;">${escapeHtml(w.title)}</td></tr>`
  ).join('');

  const htmlBody = `
    <h2 style="color:#0a0a0a;font-family:sans-serif;">New Assessment Lead</h2>
    <table style="border-collapse:collapse;width:100%;max-width:600px;font-family:sans-serif;">
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Name</td><td style="padding:8px 12px;border-bottom:1px solid #eee;">${escapeHtml(firstName)}</td></tr>
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Email</td><td style="padding:8px 12px;border-bottom:1px solid #eee;"><a href="mailto:${escapeHtml(email)}">${escapeHtml(email)}</a></td></tr>
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Risk Score</td><td style="padding:8px 12px;border-bottom:1px solid #eee;font-weight:700;font-size:18px;">${scoreNum}/${maxScoreNum}</td></tr>
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Risk Tier</td><td style="padding:8px 12px;border-bottom:1px solid #eee;font-weight:700;">${escapeHtml(safeTier)}</td></tr>
    </table>
    ${weakList ? `<h3 style="color:#0a0a0a;font-family:sans-serif;margin-top:20px;">Weak Areas</h3><table style="border-collapse:collapse;width:100%;max-width:600px;font-family:sans-serif;">${weakList}</table>` : ''}
    <p style="margin-top:20px;font-family:sans-serif;font-size:13px;color:#888;">This lead completed the Training Liability Risk Assessment on brassops.com</p>
  `;

  const weakText = safeWeakAreas.map(w => `  - ${w.level}: ${w.title}`).join('\n');

  const textBody = [
    'NEW ASSESSMENT LEAD',
    `Name: ${firstName}`,
    `Email: ${email}`,
    `Risk Score: ${scoreNum}/${maxScoreNum}`,
    `Risk Tier: ${safeTier}`,
    weakText ? `\nWeak Areas:\n${weakText}` : '',
  ].join('\n');

  // Sanitize subject line
  const safeFirst = String(firstName).replace(/[\r\n]/g, '').slice(0, 50);
  const safeSubjectTier = safeTier.replace(/[\r\n]/g, '').slice(0, 50);

  // Send email notification
  try {
    await fetch('https://api.smtp2go.com/v3/email/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: smtpKey,
        to: [recipient],
        sender: 'BrassOps Assessment <noreply@brassops.com>',
        subject: `Assessment Lead: ${safeFirst} — ${safeSubjectTier} (${scoreNum}/${maxScoreNum})`,
        html_body: htmlBody,
        text_body: textBody,
      }),
    });
  } catch (err) {
    console.error('SMTP2GO request failed');
  }

  // Add contact to Brevo
  if (brevoKey) {
    try {
      const weakAreaNames = safeWeakAreas.map(w => w.title).join(', ');

      await fetch('https://api.brevo.com/v3/contacts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'api-key': brevoKey,
        },
        body: JSON.stringify({
          email: email,
          attributes: {
            FIRSTNAME: firstName,
            RISK_SCORE: scoreNum,
            RISK_TIER: safeTier,
            WEAK_AREAS: weakAreaNames || 'None',
          },
          updateEnabled: true,
        }),
      });
    } catch (err) {
      console.error('Brevo API error');
    }
  }

  return res.status(200).json({ success: true });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
