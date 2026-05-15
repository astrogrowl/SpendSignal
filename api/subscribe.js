// ─────────────────────────────────────────────────────────────────────────────
// api/subscribe.js — SpendSignal WEB FUNNEL email handler (Vercel serverless)
//
// Sends a transactional result email via Resend after a user completes the quiz.
// Belongs to spendsignalweb (the marketing funnel), not to the mobile app.
//
// This file does NOT:
//   • Grant or enforce subscriptions
//   • Manage in-app AI credits or billing state
//   • Import anything from the mobile app (../spendsignal)
//
// Environment variable required: RESEND_API_KEY (set in Vercel project settings)
// ─────────────────────────────────────────────────────────────────────────────
export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const { name, email, profileName, profileLevel, score, loss, promo, discount, optIn, lead } = req.body || {};
  if (!email || !name) return res.status(400).json({ error: 'Missing name or email' });

  // TODO (CRM): pipe `lead` to your database / analytics sink here.
  // `lead` contains the full structured quiz result, pricing intent, UTM attribution,
  // opt-in preference, and promo details. Shape: see buildLead() in quiz.html.
  // Example: await db.leads.upsert({ where: { email: lead.email }, data: lead });
  if (lead) {
    console.log('[subscribe] lead captured', {
      email:            lead.email,
      quiz_result:      lead.quiz_result,
      recommended_plan: lead.recommended_plan,
      selected_plan:    lead.selected_plan,
      selected_period:  lead.selected_billing_period,
      reward_code:      lead.reward_code,
      weekly_tips:      lead.weekly_tips_opt_in,
      utm_source:       lead.utm_source,
    });
  }

  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) return res.status(500).json({ error: 'Email service not configured' });

  // Level-specific data
  const levelColors = { 1:'#16A34A', 2:'#CA8A04', 3:'#EA580C', 4:'#DC2626', 5:'#7F1D1D' };
  const levelBgs    = { 1:'#f0fdf4', 2:'#fefce8', 3:'#fff7ed', 4:'#fef2f2', 5:'#fef2f2' };
  const levelEmoji  = { 1:'😄', 2:'🙂', 3:'😐', 4:'😟', 5:'😰' };
  const hooks = {
    1: `You're already ahead of 80% of people — now let's push you to the top.`,
    2: `You're closer than you think. One habit shift could change everything.`,
    3: `You've got the awareness. Now let's turn it into real action.`,
    4: `Taking this quiz already puts you ahead of most people. Let's go further.`,
    5: `Taking this quiz was brave. Most people never look. That means something.`,
  };
  const subjects = {
    1: `${name}, your money score is in 👀`,
    2: `${name}, here's what's holding you back 💡`,
    3: `${name}, your spending blind spot revealed 🔍`,
    4: `${name}, we found your leak. It's bigger than you think 💸`,
    5: `${name}, this number will surprise you 😳`,
  };

  const lvl         = profileLevel || 3;
  const accentColor = levelColors[lvl] || '#7c3aed';
  const cardBg      = levelBgs[lvl]    || '#f5f3ff';
  const emoji       = levelEmoji[lvl]  || '🎯';
  const hook        = hooks[lvl]       || hooks[3];
  const subject     = subjects[lvl]    || `${name}, your SpendSignal results are in`;

  // SVG score ring
  const circ    = 314;
  const dash    = Math.round(circ * score / 100);

  // Scout image + promo URL (absolute for email clients)
  const scoutImg = `https://spendsignal.app/public/${lvl}.png`;
  const logoImg  = `https://spendsignal.app/public/LogoSS.png`;
  const promoUrl = `https://spendsignal.app/quiz?reset=1&promo=${encodeURIComponent(promo)}`;

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>${subject}</title>
</head>
<body style="margin:0;padding:0;background:#eef2ff;font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;">

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef2ff;padding:32px 0 48px;">
<tr><td align="center" style="padding:0 16px;">

  <!-- ── Card ── -->
  <table role="presentation" width="560" cellpadding="0" cellspacing="0"
    style="max-width:560px;width:100%;background:#ffffff;border-radius:24px;
           overflow:hidden;
           box-shadow:0 0 0 1px rgba(124,58,237,0.06),0 8px 60px rgba(124,58,237,0.22),0 32px 80px rgba(59,130,246,0.12);">

    <!-- ══ HEADER ══ -->
    <tr>
      <td style="background:linear-gradient(135deg,#7c3aed,#3b82f6);padding:0;">
        <!-- Logo row -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding:18px 32px 0;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="vertical-align:middle;">
                    <img src="${logoImg}" alt="SpendSignal" width="26" height="26"
                      style="display:block;border-radius:8px;"/>
                  </td>
                  <td style="padding-left:8px;vertical-align:middle;">
                    <span style="font-size:15px;font-weight:900;color:#ffffff;letter-spacing:-0.3px;">SpendSignal</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Scout hero -->
          <tr>
            <td style="text-align:center;padding:20px 32px 0;">
              <img src="${scoutImg}" alt="${emoji} Scout" width="120" height="120"
                style="display:inline-block;border-radius:50%;background:rgba(255,255,255,0.15);
                       border:3px solid rgba(255,255,255,0.4);"/>
            </td>
          </tr>
          <!-- Heading -->
          <tr>
            <td style="text-align:center;padding:16px 32px 32px;">
              <p style="margin:0 0 6px;font-size:12px;font-weight:700;
                color:rgba(255,255,255,0.7);letter-spacing:2px;text-transform:uppercase;">
                Your SpendSignal Report
              </p>
              <h1 style="margin:0;font-size:28px;font-weight:900;color:#ffffff;
                line-height:1.2;letter-spacing:-0.5px;">
                ${name}, your results<br/>are ready.
              </h1>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- ══ HOOK ══ -->
    <tr>
      <td style="padding:28px 32px 0;text-align:center;">
        <p style="margin:0;font-size:15px;color:#64748b;line-height:1.7;font-style:italic;">
          "${hook}"
        </p>
      </td>
    </tr>

    <!-- ══ SCORE RING ══ -->
    <tr>
      <td style="padding:24px 32px 20px;text-align:center;">
        <svg width="130" height="130" viewBox="0 0 120 120" style="display:block;margin:0 auto 14px;">
          <defs>
            <linearGradient id="rGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style="stop-color:#7c3aed"/>
              <stop offset="100%" style="stop-color:#3b82f6"/>
            </linearGradient>
          </defs>
          <!-- Track -->
          <circle cx="60" cy="60" r="50" fill="none" stroke="#e2e8f0" stroke-width="9"/>
          <!-- Fill — uses level color so green=good, red=bad -->
          <circle cx="60" cy="60" r="50" fill="none" stroke="${accentColor}" stroke-width="9"
            stroke-dasharray="${dash} ${circ}" stroke-linecap="round"
            transform="rotate(-90 60 60)"/>
          <!-- Score -->
          <text x="60" y="54" text-anchor="middle" font-size="24" font-weight="900"
            fill="#0f172a" font-family="Arial">${score}</text>
          <text x="60" y="70" text-anchor="middle" font-size="11"
            fill="#94a3b8" font-family="Arial">/100</text>
        </svg>
        <p style="margin:0 0 4px;font-size:18px;font-weight:800;color:#0f172a;">${profileName}</p>
        <p style="margin:0;font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;">Spending health score</p>
      </td>
    </tr>

    <!-- ══ LEAK CARD ══ -->
    <tr>
      <td style="padding:4px 32px 20px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
          style="background:${cardBg};border-radius:16px;box-shadow:0 2px 24px rgba(0,0,0,0.07);">
          <tr>
            <td style="padding:20px 24px;">
              <p style="margin:0 0 6px;font-size:11px;font-weight:700;color:${accentColor};
                text-transform:uppercase;letter-spacing:1.5px;">💸 Estimated monthly leak</p>
              <p style="margin:0 0 6px;font-size:36px;font-weight:900;color:#0f172a;letter-spacing:-1px;">${loss}</p>
              <p style="margin:0;font-size:13px;color:#64748b;line-height:1.6;">
                That's money quietly leaving every month.<br/>
                SpendSignal shows you exactly where — and how to stop it.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- ══ PROMO TICKET ══ -->
    <tr>
      <td style="padding:0 32px 24px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
          style="border-radius:16px;background:#faf5ff;overflow:hidden;box-shadow:0 0 0 1.5px rgba(167,139,250,0.35),0 4px 30px rgba(124,58,237,0.13);">
          <!-- Top: discount amount -->
          <tr>
            <td style="padding:22px 24px 16px;text-align:center;
              border-bottom:1px solid rgba(167,139,250,0.25);">

              <p style="margin:0 0 6px;font-size:11px;font-weight:700;color:#7c3aed;
                text-transform:uppercase;letter-spacing:2px;">🎁 Your exclusive discount</p>
              <p style="margin:0;font-size:52px;font-weight:900;color:#0f172a;
                letter-spacing:-2px;line-height:1.05;">
                ${discount}<span style="font-size:30px;color:#7c3aed;">%</span>
              </p>
              <p style="margin:6px 0 0;font-size:13px;color:#64748b;">off your first year — locked in for you</p>
            </td>
          </tr>
          <!-- Bottom: code pill -->
          <tr>
            <td style="padding:16px 24px 20px;text-align:center;">
              <p style="margin:0 0 10px;font-size:11px;color:#94a3b8;
                text-transform:uppercase;letter-spacing:1px;">Your code</p>
              <div style="display:inline-block;background:#0f172a;color:#ffffff;
                font-size:18px;font-weight:800;letter-spacing:3px;
                padding:11px 26px;border-radius:10px;font-family:'Courier New',monospace;">
                ${promo}
              </div>
              <p style="margin:10px 0 0;font-size:11px;color:#ef4444;font-weight:700;">
                ⏰ &nbsp;12-minute timer starts when you tap below
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- ══ CTA BUTTON ══ -->
    <tr>
      <td style="padding:0 32px 10px;">
        <!-- Gradient button via table trick for wider email client support -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td align="center"
              style="background:linear-gradient(135deg,#7c3aed,#3b82f6);
                     border-radius:50px;
                     box-shadow:0 8px 30px rgba(124,58,237,0.30);">
              <a href="${promoUrl}"
                style="display:block;padding:18px 40px;color:#ffffff;
                  font-size:16px;font-weight:800;text-decoration:none;
                  letter-spacing:-0.2px;text-align:center;">
                Claim my ${discount}% discount &rarr;
              </a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:8px 32px 4px;text-align:center;">
        <p style="margin:0;font-size:11px;color:#94a3b8;">Code auto-applied · No copy-paste needed</p>
      </td>
    </tr>
    <tr>
      <td style="padding:4px 32px 28px;text-align:center;">
        <a href="${promoUrl}"
          style="font-size:13px;font-weight:700;color:#7c3aed;text-decoration:none;">
          Or tap here to open your plan &rarr;
        </a>
      </td>
    </tr>

    <!-- ══ DIVIDER ══ -->
    <tr>
      <td style="padding:0 32px;">
        <div style="height:1px;background:linear-gradient(90deg,transparent,#e2e8f0,transparent);"></div>
      </td>
    </tr>

    <!-- ══ WHAT'S INSIDE ══ -->
    <tr>
      <td style="padding:24px 32px 8px;">
        <p style="margin:0 0 18px;font-size:13px;font-weight:700;color:#94a3b8;
          text-transform:uppercase;letter-spacing:1px;">What's waiting inside</p>
        <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
          <tr>
            <td width="42" valign="top" style="padding:0 0 16px;font-size:24px;line-height:1;">🎯</td>
            <td style="padding:0 0 16px;">
              <p style="margin:0 0 2px;font-size:14px;font-weight:700;color:#0f172a;">Personalized AI spending plan</p>
              <p style="margin:0;font-size:12px;color:#64748b;line-height:1.5;">Built around your exact profile — not generic advice</p>
            </td>
          </tr>
          <tr>
            <td width="42" valign="top" style="padding:0 0 16px;font-size:24px;line-height:1;">📊</td>
            <td style="padding:0 0 16px;">
              <p style="margin:0 0 2px;font-size:14px;font-weight:700;color:#0f172a;">Weekly leak reports</p>
              <p style="margin:0;font-size:12px;color:#64748b;line-height:1.5;">See exactly where money escapes, every week</p>
            </td>
          </tr>
          <tr>
            <td width="42" valign="top" style="padding:0 0 16px;font-size:24px;line-height:1;">🔔</td>
            <td style="padding:0 0 16px;">
              <p style="margin:0 0 2px;font-size:14px;font-weight:700;color:#0f172a;">Smart bill reminders</p>
              <p style="margin:0;font-size:12px;color:#64748b;line-height:1.5;">Never get caught off guard by a charge again</p>
            </td>
          </tr>
          <tr>
            <td width="42" valign="top" style="font-size:24px;line-height:1;">💬</td>
            <td>
              <p style="margin:0 0 2px;font-size:14px;font-weight:700;color:#0f172a;">AI financial coach</p>
              <p style="margin:0;font-size:12px;color:#64748b;line-height:1.5;">Ask anything. No judgment. Always available.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- ══ P.S. ══ -->
    <tr>
      <td style="padding:16px 32px 28px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
          style="background:#f8faff;border-radius:14px;border-left:3px solid #7c3aed;box-shadow:0 2px 20px rgba(124,58,237,0.08);">
          <tr>
            <td style="padding:16px 20px;">
              <p style="margin:0;font-size:13px;color:#64748b;line-height:1.7;">
                <strong style="color:#0f172a;">P.S.</strong> — Many people find their first spending clarity moment sooner than expected.
                <em style="color:#7c3aed;font-style:normal;font-weight:700;">Your quiz results are waiting.</em>
                Your ${discount}% code is ready when you are.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- ══ FOOTER ══ -->
    <tr>
      <td style="padding:20px 32px 28px;background:#f8fafc;border-top:1px solid #e2e8f0;
        text-align:center;border-radius:0 0 24px 24px;">
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto 10px;">
          <tr>
            <td style="vertical-align:middle;">
              <img src="${logoImg}" alt="SpendSignal" width="18" height="18"
                style="display:block;border-radius:5px;"/>
            </td>
            <td style="padding-left:6px;vertical-align:middle;">
              <span style="font-size:13px;font-weight:900;color:#7c3aed;">SpendSignal</span>
            </td>
          </tr>
        </table>
        <p style="margin:0 0 10px;font-size:11px;color:#94a3b8;">
          Built for people who are done guessing where the money goes.
        </p>
        <p style="margin:0;font-size:10px;color:#cbd5e1;line-height:1.7;">
          You received this because you completed the SpendSignal quiz.<br/>
          No spam — just your report + your one-time discount.
        </p>
      </td>
    </tr>

  </table>
  <!-- /Card -->

</td></tr>
</table>

</body>
</html>`;

  try {
    const response = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: 'SpendSignal <scout@spendsignal.app>',
        to: [email],
        subject,
        html,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      console.error('Resend error:', data);
      return res.status(response.status).json({ error: data.message || 'Email send failed' });
    }

    return res.status(200).json({ ok: true, id: data.id });
  } catch (err) {
    console.error('Subscribe error:', err);
    return res.status(500).json({ error: 'Internal error' });
  }
}
