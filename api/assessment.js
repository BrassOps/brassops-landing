export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { firstName, email, score, maxScore, tier, weakAreas } = req.body;

  if (!firstName || !email) {
    return res.status(400).json({ error: 'Missing required fields' });
  }

  const apiKey = process.env.SMTP2GO_API_KEY;
  if (!apiKey) {
    console.error('SMTP2GO_API_KEY not configured');
    return res.status(500).json({ error: 'Server configuration error' });
  }

  const recipient = 'brassops01@gmail.com';

  const weakList = (weakAreas || []).map(w =>
    `<tr><td style="padding:6px 12px;border-bottom:1px solid #eee;color:#b03020;font-weight:600;">${escapeHtml(w.level)}</td><td style="padding:6px 12px;border-bottom:1px solid #eee;">${escapeHtml(w.title)}</td></tr>`
  ).join('');

  const htmlBody = `
    <h2 style="color:#0a0a0a;font-family:sans-serif;">New Assessment Lead</h2>
    <table style="border-collapse:collapse;width:100%;max-width:600px;font-family:sans-serif;">
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Name</td><td style="padding:8px 12px;border-bottom:1px solid #eee;">${escapeHtml(firstName)}</td></tr>
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Email</td><td style="padding:8px 12px;border-bottom:1px solid #eee;"><a href="mailto:${escapeHtml(email)}">${escapeHtml(email)}</a></td></tr>
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Risk Score</td><td style="padding:8px 12px;border-bottom:1px solid #eee;font-weight:700;font-size:18px;">${score || '?'}/${maxScore || '30'}</td></tr>
      <tr><td style="padding:8px 12px;font-weight:bold;color:#555;border-bottom:1px solid #eee;">Risk Tier</td><td style="padding:8px 12px;border-bottom:1px solid #eee;font-weight:700;">${escapeHtml(tier || 'Unknown')}</td></tr>
    </table>
    ${weakList ? `<h3 style="color:#0a0a0a;font-family:sans-serif;margin-top:20px;">Weak Areas</h3><table style="border-collapse:collapse;width:100%;max-width:600px;font-family:sans-serif;">${weakList}</table>` : ''}
    <p style="margin-top:20px;font-family:sans-serif;font-size:13px;color:#888;">This lead completed the Training Liability Risk Assessment on brassops.com</p>
  `;

  const weakText = (weakAreas || []).map(w => `  - ${w.level}: ${w.title}`).join('\n');

  const textBody = [
    `NEW ASSESSMENT LEAD`,
    `Name: ${firstName}`,
    `Email: ${email}`,
    `Risk Score: ${score || '?'}/${maxScore || '30'}`,
    `Risk Tier: ${tier || 'Unknown'}`,
    weakText ? `\nWeak Areas:\n${weakText}` : '',
  ].join('\n');

  try {
    const response = await fetch('https://api.smtp2go.com/v3/email/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: apiKey,
        to: [recipient],
        sender: 'BrassOps Assessment <noreply@brassops.com>',
        subject: `Assessment Lead: ${firstName} — ${tier || 'Completed'} (${score}/${maxScore})`,
        html_body: htmlBody,
        text_body: textBody,
      }),
    });

    const data = await response.json();

    if (data.data?.succeeded > 0) {
      return res.status(200).json({ success: true });
    } else {
      console.error('SMTP2GO error:', JSON.stringify(data));
      return res.status(502).json({ error: 'Failed to send email' });
    }
  } catch (err) {
    console.error('SMTP2GO request failed:', err);
    return res.status(502).json({ error: 'Failed to send email' });
  }
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
