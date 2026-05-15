// ─────────────────────────────────────────────────────────────────────────────
// api/waitlist.js — SpendSignal WEB FUNNEL waitlist endpoint (Vercel serverless)
//
// Accepts POST submissions from download.html when the app is not yet live.
// Validates the email, sends email notifications, and returns a clean JSON response.
//
// Belongs to spendsignalweb (the marketing funnel), NOT the mobile app.
//
// This file does NOT:
//   • Grant or enforce subscriptions
//   • Import anything from the mobile app (../spendsignal)
//   • Expose any secrets to the client
//
// Environment variables (set in Vercel project settings):
//   RESEND_API_KEY  — required for email notifications
//   LEADS_EMAIL     — operator email to receive lead notifications
//                     e.g. "you@gmail.com". If not set, only console logs.
//
// TODO (database): When you add Supabase to spendsignalweb, persist leads here:
//
//   import { createClient } from '@supabase/supabase-js'
//   const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY)
//   const { error } = await supabase.from('waitlist_leads').insert([lead])
//   if (error) console.error('[waitlist] db insert error', error)
//
//   Table: waitlist_leads
//   Columns: id, email, first_name, source, quiz_result, recommended_plan,
//            selected_plan, selected_billing_period, reward_code, utm_source,
//            utm_medium, utm_campaign, utm_content, utm_term, created_at
// ─────────────────────────────────────────────────────────────────────────────

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') {
    return res.status(405).json({
      success: false,
      error: 'METHOD_NOT_ALLOWED',
      message: 'Method not allowed.',
    });
  }

  const body = req.body || {};

  // ── Validate ──────────────────────────────────────────────────────────────
  const rawEmail = (body.email || '').toString().trim().toLowerCase();

  if (!rawEmail) {
    return res.status(400).json({
      success: false,
      error: 'VALIDATION_ERROR',
      message: 'Please enter your email address.',
    });
  }
  if (!isValidEmail(rawEmail)) {
    return res.status(400).json({
      success: false,
      error: 'VALIDATION_ERROR',
      message: 'Please enter a valid email address.',
    });
  }

  // ── Build clean lead ──────────────────────────────────────────────────────
  const lead = {
    email:                   rawEmail,
    first_name:              (body.first_name || '').toString().trim() || null,
    source:                  (body.source || 'download').toString().trim(),
    quiz_result:             (body.quiz_result   || body.quizResult    || '').toString().trim() || null,
    recommended_plan:        (body.recommended_plan || body.recommendedPlan || '').toString().trim() || null,
    selected_plan:           (body.selected_plan || body.plan          || '').toString().trim() || null,
    selected_billing_period: (body.selected_billing_period || body.period || '').toString().trim() || null,
    reward_code:             (body.reward_code   || body.rewardCode    || '').toString().trim() || null,
    utm_source:              (body.utm_source    || '').toString().trim() || null,
    utm_medium:              (body.utm_medium    || '').toString().trim() || null,
    utm_campaign:            (body.utm_campaign  || '').toString().trim() || null,
    utm_content:             (body.utm_content   || '').toString().trim() || null,
    utm_term:                (body.utm_term      || '').toString().trim() || null,
    created_at:              new Date().toISOString(),
  };

  // ── Server log (always — visible in Vercel function logs) ─────────────────
  console.log('[waitlist] new signup', {
    email:            lead.email,
    plan:             lead.selected_plan,
    quiz_result:      lead.quiz_result,
    recommended_plan: lead.recommended_plan,
    reward_code:      lead.reward_code,
    source:           lead.source,
    utm_source:       lead.utm_source,
    created_at:       lead.created_at,
  });

  // ── Email notifications via Resend ────────────────────────────────────────
  const apiKey     = process.env.RESEND_API_KEY;
  const leadsEmail = process.env.LEADS_EMAIL; // operator notification target

  if (!apiKey) {
    // No email service — lead is in Vercel logs but not persisted elsewhere.
    // Configure RESEND_API_KEY + LEADS_EMAIL in Vercel project settings to fix.
    console.warn('[waitlist] RESEND_API_KEY not set — email notifications skipped. Lead logged above only.');
    return res.status(200).json({ success: true, message: "You're on the list." });
  }

  const notifyPromises = [];

  // 1) Operator notification — every signup lands in LEADS_EMAIL inbox
  if (leadsEmail) {
    notifyPromises.push(
      sendEmail(apiKey, {
        to:      leadsEmail,
        subject: `🦝 Waitlist signup — ${lead.email}`,
        html:    buildOperatorEmail(lead),
      }).catch(err => console.error('[waitlist] operator notify failed', err.message))
    );
  } else {
    console.warn('[waitlist] LEADS_EMAIL not set — operator notification skipped. Set it in Vercel to receive lead emails.');
  }

  // 2) User confirmation — so the lead has a paper trail
  notifyPromises.push(
    sendEmail(apiKey, {
      to:      lead.email,
      subject: `You're on the SpendSignal waitlist 🦝`,
      html:    buildConfirmEmail(lead),
    }).catch(err => console.error('[waitlist] user confirm failed', err.message))
  );

  // Fire both concurrently — email failure does not fail the signup
  await Promise.allSettled(notifyPromises);

  return res.status(200).json({
    success: true,
    message: "You're on the list.",
  });
}

// ── Resend helper ─────────────────────────────────────────────────────────────

async function sendEmail(apiKey, { to, subject, html }) {
  const r = await fetch('https://api.resend.com/emails', {
    method:  'POST',
    headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from:    'SpendSignal <scout@spendsignal.app>',
      to:      [to],
      subject,
      html,
    }),
  });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error(data.message || `Resend ${r.status}`);
  }
  return r.json();
}

// ── Email templates ───────────────────────────────────────────────────────────

function buildOperatorEmail(lead) {
  const rows = Object.entries(lead)
    .filter(([, v]) => v !== null && v !== '')
    .map(([k, v]) => `
      <tr>
        <td style="padding:6px 16px 6px 0;font-size:13px;color:#64748b;white-space:nowrap;vertical-align:top;">${k}</td>
        <td style="padding:6px 0;font-size:13px;color:#0f172a;font-weight:600;">${String(v).replace(/</g,'&lt;')}</td>
      </tr>`)
    .join('');

  return `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
<tr><td align="center">
<table width="520" cellpadding="0" cellspacing="0" style="max-width:520px;width:100%;background:#ffffff;border-radius:16px;padding:28px 32px;box-shadow:0 2px 16px rgba(0,0,0,0.08);">
<tr><td>
  <p style="margin:0 0 4px;font-size:11px;font-weight:700;color:#7c3aed;text-transform:uppercase;letter-spacing:1.5px;">SpendSignal · Waitlist</p>
  <h2 style="margin:0 0 6px;font-size:20px;font-weight:900;color:#0f172a;">New waitlist signup</h2>
  <p style="margin:0 0 24px;font-size:14px;color:#64748b;">${lead.email}</p>
  <table style="width:100%;border-collapse:collapse;border-top:1px solid #e2e8f0;">
    <tr><td style="padding:12px 0 6px;font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;" colspan="2">Lead details</td></tr>
    ${rows}
  </table>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>`;
}

function buildConfirmEmail(lead) {
  const name     = lead.first_name ? `, ${lead.first_name}` : '';
  const planName = lead.selected_plan
    ? lead.selected_plan.charAt(0).toUpperCase() + lead.selected_plan.slice(1)
    : null;

  const planBlock = planName
    ? `<p style="margin:0 0 16px;font-size:15px;color:#64748b;line-height:1.65;text-align:center;">
        We'll have your <strong style="color:#0f172a;">${planName} plan</strong> details waiting when the app goes live.
       </p>`
    : '';

  const codeBlock = lead.reward_code
    ? `<div style="background:#faf5ff;border:1.5px dashed rgba(167,139,250,0.55);border-radius:12px;padding:14px 20px;margin:20px 0;text-align:center;">
         <p style="margin:0 0 4px;font-size:11px;font-weight:700;color:#7c3aed;text-transform:uppercase;letter-spacing:1.2px;">🎁 Your reward code</p>
         <p style="margin:0;font-size:22px;font-weight:900;letter-spacing:3px;color:#0f172a;font-family:'Courier New',monospace;">${lead.reward_code}</p>
         <p style="margin:6px 0 0;font-size:12px;color:#94a3b8;">Saved for you — apply at checkout.</p>
       </div>`
    : '';

  return `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/></head>
<body style="margin:0;padding:0;background:#eef2ff;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="max-width:480px;width:100%;background:#ffffff;border-radius:20px;padding:36px 32px;box-shadow:0 4px 40px rgba(124,58,237,0.13);">
<tr><td style="text-align:center;">
  <p style="margin:0 0 8px;font-size:42px;line-height:1;">🦝</p>
  <h1 style="margin:0 0 14px;font-size:24px;font-weight:900;color:#0f172a;">You're on the list${name}.</h1>
  <p style="margin:0 0 16px;font-size:15px;color:#64748b;line-height:1.65;">
    We'll send your SpendSignal download link the moment the app is live — with your plan and details already saved.
  </p>
  ${planBlock}
  ${codeBlock}
  <p style="margin:28px 0 0;font-size:11px;color:#cbd5e1;line-height:1.6;">
    SpendSignal · <a href="https://spendsignal.app" style="color:#7c3aed;text-decoration:none;">spendsignal.app</a><br/>
    You received this because you signed up for the waitlist.
  </p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>`;
}
