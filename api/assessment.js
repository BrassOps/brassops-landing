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
  weakAreaId: 50,
  weakAreasMax: 20,
};

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Brevo list IDs per risk tier
const BREVO_LISTS = {
  'High Risk': 5,
  'Elevated Risk': 6,
  'Moderate Risk': 7,
  'Strong': 8,
};

// BrassOps solutions for each assessment question — used in results email
const SOLUTIONS = {
  readiness: {
    feature: 'Officer Readiness Dashboard',
    desc: "Real-time color-coded status for every officer — green, yellow, red — visible to range masters and command staff instantly. No reports to pull, no spreadsheets to check.",
  },
  weapons: {
    feature: 'Weapon-Specific Performance Monitoring',
    desc: 'Every qualification links to the specific weapon by serial number. Per-weapon accuracy trends, round counts, and reliability tracking across your entire fleet.',
  },
  remedial: {
    feature: 'Auto Remedial Enrollment',
    desc: 'The moment a score fails, a remedial case is created automatically with a structured workflow — coaching plan, milestones, escalation paths. Every step time-stamped.',
  },
  judgment: {
    feature: 'Dry-Fire Training + AI Shot Analysis',
    desc: 'Structured practice logging between range days plus AI-powered target diagnostics that go beyond marksmanship to evaluate patterns and recommend corrective drills.',
  },
  scoring: {
    feature: 'Mobile Qualification Logging',
    desc: "Scores entered from your phone on the firing line, timestamped at the moment of the event. No paper transcription. No delayed data entry. Defensible from the second it's recorded.",
  },
  record_fields: {
    feature: 'Qualification Tracking',
    desc: 'Every session automatically captures officer ID, weapon serial, course of fire, score, threshold, instructor, and timestamp. All seven fields, every time, without extra effort.',
  },
  instructor_certs: {
    feature: 'Automated Alerts',
    desc: 'Instructor certifications tracked in the same system with automatic expiration alerts. No lapsed certs means no invalid qualifications — protecting every record your instructors touch.',
  },
  expiration_alerts: {
    feature: 'Automated Alerts',
    desc: 'Configurable warnings at 90, 60, and 30 days before any qualification expires. The system watches continuously so qualifications can never silently lapse.',
  },
  subpoena_time: {
    feature: 'Audit-Ready Records',
    desc: 'Complete training history for any officer generated in seconds — every qualification, every remedial case, every coaching note. Time-stamped, searchable, and defensible.',
  },
  audit_program: {
    feature: 'Performance Analytics + Behavioral Scoring',
    desc: 'Continuous monitoring surfaces gaps automatically. Behavioral scoring identifies patterns across officers without waiting for an annual review. Issues found in real time, not under subpoena.',
  },
};

// Tier-to-color mapping for the results email
const TIER_COLORS = {
  'Strong': { bg: '#166534', accent: '#22c55e' },
  'Moderate Risk': { bg: '#92400e', accent: '#f59e0b' },
  'Elevated Risk': { bg: '#9a3412', accent: '#f97316' },
  'High Risk': { bg: '#991b1b', accent: '#ef4444' },
};

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
        typeof w.title === 'string' && w.title.length <= LIMITS.weakAreaTitle &&
        typeof w.id === 'string' && w.id.length <= LIMITS.weakAreaId
      )
    : [];

  const smtpKey = process.env.SMTP2GO_API_KEY;
  const brevoKey = process.env.BREVO_API_KEY;

  if (!smtpKey) {
    console.error('SMTP2GO_API_KEY not configured');
    return res.status(500).json({ error: 'Server configuration error' });
  }

  const recipient = process.env.CONTACT_RECIPIENT || 'brassops01@gmail.com';

  // ── Admin notification email ──
  const adminWeakList = safeWeakAreas.map(w =>
    `<tr><td style="padding:6px 12px;border-bottom:1px solid #eee;color:#b03020;font-weight:600;">${escapeHtml(w.level)}</td><td style="padding:6px 12px;border-bottom:1px solid #eee;">${escapeHtml(w.title)}</td></tr>`
  ).join('');

  const adminHtmlBody = `
    <h2 style="color:#0a0a0a;font-family:sans-serif;">New Assessment Lead</h2>
    <table style="border-collapse:collapse;width:100%;max-width:600px;font-family:sans-serif;">
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Name</td><td style="padding:8px 12px;border-bottom:1px solid #eee;">${escapeHtml(firstName)}</td></tr>
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Email</td><td style="padding:8px 12px;border-bottom:1px solid #eee;"><a href="mailto:${escapeHtml(email)}">${escapeHtml(email)}</a></td></tr>
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Risk Score</td><td style="padding:8px 12px;border-bottom:1px solid #eee;font-weight:700;font-size:18px;">${scoreNum}/${maxScoreNum}</td></tr>
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Risk Tier</td><td style="padding:8px 12px;border-bottom:1px solid #eee;font-weight:700;">${escapeHtml(safeTier)}</td></tr>
    </table>
    ${adminWeakList ? `<h3 style="color:#0a0a0a;font-family:sans-serif;margin-top:20px;">Weak Areas</h3><table style="border-collapse:collapse;width:100%;max-width:600px;font-family:sans-serif;">${adminWeakList}</table>` : ''}
    <p style="margin-top:20px;font-family:sans-serif;font-size:13px;color:#888;">This lead completed the Training Liability Risk Assessment on brassops.com</p>
  `;

  const adminWeakText = safeWeakAreas.map(w => `  - ${w.level}: ${w.title}`).join('\n');

  const adminTextBody = [
    'NEW ASSESSMENT LEAD',
    `Name: ${firstName}`,
    `Email: ${email}`,
    `Risk Score: ${scoreNum}/${maxScoreNum}`,
    `Risk Tier: ${safeTier}`,
    adminWeakText ? `\nWeak Areas:\n${adminWeakText}` : '',
  ].join('\n');

  const safeFirst = String(firstName).replace(/[\r\n]/g, '').slice(0, 50);
  const safeSubjectTier = safeTier.replace(/[\r\n]/g, '').slice(0, 50);

  try {
    await fetch('https://api.smtp2go.com/v3/email/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: smtpKey,
        to: [recipient],
        sender: 'BrassOps Assessment <noreply@brassops.com>',
        subject: `Assessment Lead: ${safeFirst} — ${safeSubjectTier} (${scoreNum}/${maxScoreNum})`,
        html_body: adminHtmlBody,
        text_body: adminTextBody,
      }),
    });
  } catch (err) {
    console.error('SMTP2GO admin email failed:', err.message);
  }

  // ── Results email to the taker ──
  try {
    const tierColor = TIER_COLORS[safeTier] || TIER_COLORS['High Risk'];

    const findingsHtml = safeWeakAreas.map(w => {
      const sol = SOLUTIONS[w.id];
      const solutionBlock = sol
        ? `<div style="margin-top:12px;padding:14px 16px;background:#f0fdf4;border-left:3px solid #22c55e;border-radius:0 6px 6px 0;">
             <div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#16a34a;margin-bottom:4px;">How Brass<span style="color:#ef4444">Ops</span> Solves This</div>
             <div style="font-size:14px;color:#1a1a1a;font-weight:700;margin-bottom:4px;">${escapeHtml(sol.feature)}</div>
             <div style="font-size:13px;color:#444;line-height:1.6;">${escapeHtml(sol.desc)}</div>
           </div>`
        : '';
      return `
        <div style="background:#ffffff;border:1px solid #e4e4e7;border-left:3px solid #ef4444;border-radius:8px;padding:16px 18px;margin-bottom:12px;">
          <div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#dc2626;margin-bottom:4px;">${escapeHtml(w.level)}</div>
          <div style="font-size:16px;font-weight:700;color:#0a0a0a;">${escapeHtml(w.title)}</div>
          ${solutionBlock}
        </div>`;
    }).join('');

    const takerHtmlBody = `<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f5f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f5f5f7;">
    <tr>
      <td align="center" style="padding:24px 16px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.06);">

          <!-- Header -->
          <tr>
            <td style="background:#0a0a0a;padding:24px 32px;text-align:center;">
              <div style="font-size:28px;font-weight:800;letter-spacing:2px;color:#ffffff;">Brass<span style="color:#ef4444">Ops</span></div>
              <div style="font-size:11px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:#888;margin-top:4px;">Range Intelligence Platform</div>
            </td>
          </tr>

          <!-- Score hero -->
          <tr>
            <td style="background:${tierColor.bg};padding:36px 32px;text-align:center;color:#ffffff;">
              <div style="font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;opacity:0.75;margin-bottom:12px;">Your Liability Risk Score</div>
              <div style="font-size:56px;font-weight:800;line-height:1;margin-bottom:8px;">${scoreNum}<span style="font-size:24px;opacity:0.5;">/${maxScoreNum}</span></div>
              <div style="font-size:22px;font-weight:700;margin-bottom:10px;">${escapeHtml(safeTier)}</div>
            </td>
          </tr>

          <!-- Intro -->
          <tr>
            <td style="padding:32px 32px 20px 32px;color:#1a1a1a;">
              <p style="font-size:16px;line-height:1.6;margin:0 0 12px 0;">Hi ${escapeHtml(firstName)},</p>
              <p style="font-size:15px;line-height:1.65;color:#444;margin:0 0 16px 0;">
                Thanks for taking the Brass<span style="color:#ef4444">Ops</span> Training Liability Risk Assessment. Below are your detailed findings along with how Brass<span style="color:#ef4444">Ops</span> addresses each one.
              </p>
              <p style="font-size:15px;line-height:1.65;color:#444;margin:0;">
                These are the exact documentation gaps that plaintiff's attorneys target in failure-to-train litigation. The good news: every one of them is preventable.
              </p>
            </td>
          </tr>

          ${safeWeakAreas.length > 0 ? `
          <!-- Findings -->
          <tr>
            <td style="padding:0 32px 8px 32px;">
              <div style="font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#dc2626;margin-bottom:6px;">Your Findings</div>
              <div style="font-size:18px;font-weight:700;color:#0a0a0a;margin-bottom:16px;">${safeWeakAreas.length} ${safeWeakAreas.length === 1 ? 'Area' : 'Areas'} to Address</div>
              ${findingsHtml}
            </td>
          </tr>
          ` : `
          <tr>
            <td style="padding:0 32px 8px 32px;">
              <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:20px;text-align:center;">
                <div style="font-size:16px;font-weight:700;color:#166534;margin-bottom:6px;">Strong Position</div>
                <div style="font-size:14px;color:#15803d;line-height:1.6;">Your agency has strong documentation practices in place. Plaintiff's attorneys would struggle to construct a deliberate indifference argument against your current program.</div>
              </div>
            </td>
          </tr>
          `}

          <!-- CTA -->
          <tr>
            <td style="padding:24px 32px 32px 32px;">
              <div style="background:linear-gradient(135deg,rgba(239,68,68,0.08),rgba(239,68,68,0.03));border:1px solid rgba(239,68,68,0.12);border-radius:12px;padding:28px;text-align:center;">
                <div style="font-size:20px;font-weight:800;color:#0a0a0a;margin-bottom:8px;">See How Brass<span style="color:#ef4444">Ops</span> Protects Your Department</div>
                <div style="font-size:14px;color:#444;line-height:1.6;margin-bottom:18px;">A 15-minute demo shows exactly how Brass<span style="color:#ef4444">Ops</span> closes every gap your assessment identified. No slides — just the platform with your workflow.</div>
                <a href="https://brassops.com/contact" style="display:inline-block;background:linear-gradient(135deg,#ef4444,#dc2626);color:#ffffff;font-weight:700;letter-spacing:1px;text-transform:uppercase;font-size:14px;text-decoration:none;padding:14px 32px;border-radius:10px;">Schedule a 15-Minute Demo</a>
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#fafafa;padding:24px 32px;text-align:center;border-top:1px solid #eeeeee;">
              <div style="font-size:13px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#888;margin-bottom:4px;">Brass<span style="color:#ef4444">Ops</span></div>
              <div style="font-size:11px;color:#999;font-style:italic;margin-bottom:12px;">Built for those who train to protect.</div>
              <div style="font-size:11px;color:#aaa;">
                <a href="https://brassops.com/privacy" style="color:#888;text-decoration:none;margin:0 8px;">Privacy Policy</a>
                <a href="https://brassops.com/terms" style="color:#888;text-decoration:none;margin:0 8px;">Terms of Service</a>
              </div>
              <div style="font-size:10px;color:#bbb;margin-top:12px;">&copy; 2026 BrassOps. All rights reserved.</div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>`;

    const takerTextLines = [
      `Hi ${firstName},`,
      '',
      'Thanks for taking the BrassOps Training Liability Risk Assessment.',
      '',
      `YOUR LIABILITY RISK SCORE: ${scoreNum}/${maxScoreNum}`,
      `RISK TIER: ${safeTier}`,
      '',
    ];

    if (safeWeakAreas.length > 0) {
      takerTextLines.push('YOUR FINDINGS:');
      takerTextLines.push('');
      safeWeakAreas.forEach(w => {
        takerTextLines.push(`[${w.level}] ${w.title}`);
        const sol = SOLUTIONS[w.id];
        if (sol) {
          takerTextLines.push(`  How BrassOps solves it: ${sol.feature}`);
          takerTextLines.push(`  ${sol.desc}`);
        }
        takerTextLines.push('');
      });
    } else {
      takerTextLines.push('Strong Position — your agency has strong documentation practices in place.');
      takerTextLines.push('');
    }

    takerTextLines.push('───────────────────────────────');
    takerTextLines.push('Ready to see how BrassOps closes every gap? Schedule a 15-minute demo:');
    takerTextLines.push('https://brassops.com/contact');
    takerTextLines.push('');
    takerTextLines.push('BrassOps — Built for those who train to protect.');
    takerTextLines.push('© 2026 BrassOps');

    await fetch('https://api.smtp2go.com/v3/email/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: smtpKey,
        to: [email],
        sender: 'BrassOps <noreply@brassops.com>',
        subject: 'Your BrassOps Training Liability Risk Assessment Results',
        html_body: takerHtmlBody,
        text_body: takerTextLines.join('\n'),
      }),
    });
  } catch (err) {
    console.error('SMTP2GO taker email failed:', err.message);
  }

  // ── Add contact to Brevo with correct list ──
  if (brevoKey) {
    try {
      const weakAreaNames = safeWeakAreas.map(w => w.title).join(', ');
      const listId = BREVO_LISTS[safeTier];

      const brevoBody = {
        email: email,
        attributes: {
          FIRSTNAME: firstName,
          RISK_SCORE: scoreNum,
          RISK_TIER: safeTier,
          WEAK_AREAS: weakAreaNames || 'None',
        },
        updateEnabled: true,
      };
      if (listId) {
        brevoBody.listIds = [listId];
      }

      const brevoRes = await fetch('https://api.brevo.com/v3/contacts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'api-key': brevoKey,
        },
        body: JSON.stringify(brevoBody),
      });

      if (!brevoRes.ok) {
        const errText = await brevoRes.text();
        console.error('Brevo API error:', brevoRes.status, errText);
      }
    } catch (err) {
      console.error('Brevo request failed:', err.message);
    }
  } else {
    console.warn('BREVO_API_KEY not configured — contact not synced');
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
