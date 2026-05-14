/**
 * SpendSignal — test email sender
 * Usage: RESEND_API_KEY=re_xxxx node test-email.mjs
 *
 * Sends a Level 4 (Reactive Spender) test email to your inbox.
 */

const API_KEY = process.env.RESEND_API_KEY;
if (!API_KEY) {
  console.error('❌  Missing RESEND_API_KEY. Run: RESEND_API_KEY=re_xxxx node test-email.mjs');
  process.exit(1);
}

// ── Test payload (change these to whatever you want to test) ──
const payload = {
  name:         'Nicolas',
  email:        'nicolasburgosnettle@gmail.com',
  profileName:  'The Reactive Spender',
  profileLevel: 4,
  score:        30,
  loss:         '$390/mo',
  promo:        'NICO_MAY45',
  discount:     45,
  optIn:        false,
};

// ── Call the serverless function logic directly ──
const levelColors     = { 1:'#16A34A', 2:'#CA8A04', 3:'#EA580C', 4:'#DC2626', 5:'#7F1D1D' };
const levelEmoji      = { 1:'😄', 2:'🙂', 3:'😐', 4:'😟', 5:'😰' };
const hooks = {
  1: `You're already ahead of 80% of people. Let's push you to the top.`,
  2: `You're closer than you think. One shift could change everything.`,
  3: `You've got the awareness. Now let's turn it into action.`,
  4: `The fact that you took this quiz already puts you ahead. Let's go further.`,
  5: `Taking this quiz was brave. Most people never look. That means something.`,
};
const subjects = {
  1: `${payload.name}, your money score is in 👀`,
  2: `${payload.name}, here's what's holding you back 💡`,
  3: `${payload.name}, your spending blind spot revealed 🔍`,
  4: `${payload.name}, we found the leak. It's bigger than you think 💸`,
  5: `${payload.name}, this number will surprise you 😳`,
};

const { name, email, profileName, profileLevel, score, loss, promo, discount } = payload;
const ringColor    = levelColors[profileLevel] || '#7c3aed';
const levelMoji    = levelEmoji[profileLevel]  || '🎯';
const openingHook  = hooks[profileLevel]       || hooks[3];
const subject      = subjects[profileLevel]    || `${name}, your SpendSignal results are in`;
const circumference = 314.16;
const dashFill     = Math.round(circumference * score / 100);
const promoUrl     = `https://spendsignal.app/quiz?reset=1&promo=${encodeURIComponent(promo)}`;

const html = `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/></head>
<body style="margin:0;padding:0;background:#0f0f14;font-family:Arial,Helvetica,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0f0f14;padding:32px 0 48px;">
  <tr><td align="center">
    <table role="presentation" width="560" cellpadding="0" cellspacing="0"
      style="max-width:560px;width:100%;background:#1a1a24;border-radius:24px;overflow:hidden;">
      <tr>
        <td style="background:${ringColor};padding:28px 40px 24px;text-align:center;">
          <p style="margin:0 0 6px;font-size:11px;font-weight:700;color:rgba(255,255,255,0.65);letter-spacing:2px;text-transform:uppercase;">SpendSignal · Your Results</p>
          <h1 style="margin:0;font-size:30px;font-weight:900;color:#ffffff;line-height:1.15;letter-spacing:-0.5px;">${levelMoji}&nbsp; ${name},<br/>your report is ready.</h1>
        </td>
      </tr>
      <tr>
        <td style="padding:24px 40px 0;text-align:center;">
          <p style="margin:0;font-size:15px;color:#94a3b8;font-style:italic;line-height:1.6;">"${openingHook}"</p>
        </td>
      </tr>
      <tr>
        <td style="padding:28px 40px 24px;text-align:center;">
          <svg width="140" height="140" viewBox="0 0 120 120" style="display:block;margin:0 auto 16px;">
            <circle cx="60" cy="60" r="50" fill="none" stroke="#2a2a38" stroke-width="10"/>
            <circle cx="60" cy="60" r="50" fill="none" stroke="${ringColor}" stroke-width="10"
              stroke-dasharray="${dashFill} ${Math.ceil(circumference)}" stroke-linecap="round" transform="rotate(-90 60 60)"/>
            <text x="60" y="55" text-anchor="middle" font-size="22" font-weight="900" fill="#ffffff" font-family="Arial">${score}</text>
            <text x="60" y="70" text-anchor="middle" font-size="11" fill="#64748b" font-family="Arial">/100</text>
          </svg>
          <p style="margin:0 0 4px;font-size:19px;font-weight:800;color:#ffffff;">${profileName}</p>
          <p style="margin:0;font-size:12px;color:#475569;text-transform:uppercase;letter-spacing:1px;">Spending health score</p>
        </td>
      </tr>
      <tr>
        <td style="padding:0 32px 24px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
            style="background:#200e0e;border-radius:14px;border:1px solid ${ringColor}44;">
            <tr>
              <td style="padding:20px 22px;">
                <p style="margin:0 0 6px;font-size:11px;font-weight:700;color:${ringColor};text-transform:uppercase;letter-spacing:1.5px;">💸 Your estimated monthly leak</p>
                <p style="margin:0 0 8px;font-size:34px;font-weight:900;color:#ffffff;letter-spacing:-1px;">${loss}</p>
                <p style="margin:0;font-size:13px;color:#64748b;line-height:1.5;">That's money leaving quietly every month. SpendSignal shows you exactly where — and how to stop it.</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="padding:0 32px 28px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
            style="background:#111827;border-radius:16px;border:1.5px solid #2d2d40;overflow:hidden;">
            <tr>
              <td style="padding:22px 24px 18px;text-align:center;border-bottom:2px dashed #2d2d40;">
                <p style="margin:0 0 4px;font-size:11px;font-weight:700;color:${ringColor};text-transform:uppercase;letter-spacing:2px;">🎁 Your exclusive reward</p>
                <p style="margin:0;font-size:48px;font-weight:900;color:#ffffff;letter-spacing:-2px;line-height:1.1;">${discount}<span style="font-size:28px;">%</span></p>
                <p style="margin:4px 0 0;font-size:13px;color:#475569;">off your first year — locked in for you</p>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 24px;text-align:center;">
                <p style="margin:0 0 10px;font-size:11px;color:#475569;letter-spacing:1px;text-transform:uppercase;">Promo code</p>
                <div style="display:inline-block;background:#0f172a;border:1px solid ${ringColor}66;color:${ringColor};font-size:20px;font-weight:800;letter-spacing:3px;padding:12px 28px;border-radius:10px;font-family:'Courier New',monospace;">${promo}</div>
                <p style="margin:10px 0 0;font-size:11px;color:#ef4444;font-weight:700;">⏰ &nbsp;Timer starts when you click below</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="padding:0 32px 12px;">
          <a href="${promoUrl}" style="display:block;background:${ringColor};color:#ffffff;font-size:17px;font-weight:800;padding:20px 32px;border-radius:14px;text-decoration:none;text-align:center;">Claim my ${discount}% discount &nbsp;→</a>
        </td>
      </tr>
      <tr><td style="padding:0 32px 4px;text-align:center;"><p style="margin:10px 0 0;font-size:11px;color:#334155;">Code auto-applied · No copy-paste needed</p></td></tr>
      <tr><td style="padding:4px 32px 28px;text-align:center;"><a href="${promoUrl}" style="font-size:13px;font-weight:700;color:#7c3aed;text-decoration:none;">Or tap here to open your plan &rarr;</a></td></tr>
      <tr>
        <td style="padding:0 32px 28px;">
          <p style="margin:0 0 16px;font-size:13px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;">What's waiting inside</p>
          <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
            <tr><td width="40" valign="middle" style="font-size:22px;padding:8px 0;">🎯</td><td style="padding:8px 0 8px 8px;border-bottom:1px solid #1e1e2e;"><p style="margin:0;font-size:14px;font-weight:700;color:#e2e8f0;">Personalized AI spending plan</p><p style="margin:3px 0 0;font-size:12px;color:#475569;">Built around your exact profile — not generic advice</p></td></tr>
            <tr><td width="40" valign="middle" style="font-size:22px;padding:8px 0;">📊</td><td style="padding:8px 0 8px 8px;border-bottom:1px solid #1e1e2e;"><p style="margin:0;font-size:14px;font-weight:700;color:#e2e8f0;">Weekly leak reports</p><p style="margin:3px 0 0;font-size:12px;color:#475569;">See exactly where money escapes, every week</p></td></tr>
            <tr><td width="40" valign="middle" style="font-size:22px;padding:8px 0;">🔔</td><td style="padding:8px 0 8px 8px;border-bottom:1px solid #1e1e2e;"><p style="margin:0;font-size:14px;font-weight:700;color:#e2e8f0;">Smart bill reminders</p><p style="margin:3px 0 0;font-size:12px;color:#475569;">Never get caught off guard by a charge again</p></td></tr>
            <tr><td width="40" valign="middle" style="font-size:22px;padding:8px 0;">💬</td><td style="padding:8px 0 8px 8px;"><p style="margin:0;font-size:14px;font-weight:700;color:#e2e8f0;">AI financial coach</p><p style="margin:3px 0 0;font-size:12px;color:#475569;">Ask anything. No judgment. Always available.</p></td></tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="padding:0 32px 28px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
            style="background:#0f172a;border-radius:12px;border-left:3px solid ${ringColor};">
            <tr><td style="padding:16px 18px;">
              <p style="margin:0;font-size:13px;color:#94a3b8;line-height:1.6;"><strong style="color:#e2e8f0;">P.S.</strong> — Most people who start SpendSignal notice their first real saving within the first week. Not months. <em style="color:#e2e8f0;">One week.</em> Your ${discount}% code is ready when you are.</p>
            </td></tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="padding:20px 32px 28px;border-top:1px solid #1e1e2e;text-align:center;">
          <p style="margin:0 0 4px;font-size:13px;font-weight:800;color:#475569;">SpendSignal</p>
          <p style="margin:0 0 12px;font-size:11px;color:#334155;">Built for people who are done guessing where the money goes.</p>
          <p style="margin:0;font-size:10px;color:#1e293b;line-height:1.6;">You received this because you completed the SpendSignal quiz.<br/>No spam. Just your report + your one-time discount.</p>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body></html>`;

// ── Send via Resend ──
console.log(`📧 Sending test email to ${email}...`);
const res = await fetch('https://api.resend.com/emails', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${API_KEY}`, 'Content-Type': 'application/json' },
  body: JSON.stringify({ from: 'SpendSignal <scout@spendsignal.app>', to: [email], subject, html }),
});

const data = await res.json();
if (res.ok) {
  console.log(`✅ Sent! Email ID: ${data.id}`);
  console.log(`📬 Check ${email} — subject: "${subject}"`);
} else {
  console.error('❌ Failed:', data);
}
