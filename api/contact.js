export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { firstName, lastName, email, department, role, interest, message } = req.body;

  if (!firstName || !lastName || !email) {
    return res.status(400).json({ error: 'Missing required fields' });
  }

  const apiKey = process.env.SMTP2GO_API_KEY;
  if (!apiKey) {
    console.error('SMTP2GO_API_KEY not configured');
    return res.status(500).json({ error: 'Server configuration error' });
  }

  const recipient = 'brassops01@gmail.com';

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

  try {
    const response = await fetch('https://api.smtp2go.com/v3/email/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: apiKey,
        to: [recipient],
        sender: `BrassOps Contact Form <noreply@brassops.com>`,
        subject: `New Contact: ${firstName} ${lastName} — ${interest || 'General'}`,
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
