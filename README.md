# SpendSignal — Web Funnel

Marketing funnel for the SpendSignal mobile app.

## Architecture

There are two separate local projects. Do not mix them.

| Project | Path | Purpose |
|---|---|---|
| **Web funnel** | `ClaudeShit/spendsignalweb` | This project. Marketing website and quiz flow. |
| **Mobile app** | `ClaudeShit/spendsignal` | The actual product users install on their phone. |

## What this project does

- Hosts the quiz that profiles users' spending behavior
- Displays a personalized result and plan recommendation
- Captures email and sends a transactional result email via Resend
- Presents plan pricing and a discount/reward code
- Hands users off to checkout links, app store links, or a waitlist

## What this project does NOT do

- Import or depend on any file from `../spendsignal`
- Enforce real AI credit limits or usage metering
- Manage subscription billing state
- Replicate mobile app screens or components

## Key files

| File | Role |
|---|---|
| `quiz.html` | Entire funnel — quiz, result, paywall, email capture |
| `download.html` | Post-paywall handoff page — app store buttons or waitlist |
| `api/subscribe.js` | Vercel serverless function — sends result email via Resend |
| `index.html` | Marketing homepage |

## Config in quiz.html

**`MARKETING_PLANS`** — plan names, credit counts, pricing, trial info.
These are marketing display values. Real entitlement enforcement lives in the mobile app.

**`FUNNEL_DESTINATIONS`** — checkout URLs, app store URLs, fallback download URL.
Do not hardcode `https://spendsignal.app/signup` unless that route intentionally exists as a web signup flow. Use this config instead and leave URLs empty to fall back to `/download`.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `RESEND_API_KEY` | Yes | Resend API key for transactional emails |

Set via Vercel project settings — never commit to source control.

## Post-funnel flow

```
Ad / social content
  → quiz.html (quiz → result → paywall → email capture)
    → checkout URL (if configured in FUNNEL_DESTINATIONS)
    → /download (if no checkout URL yet)
      → App Store / Play Store (if configured)
      → Waitlist email form (if app not yet live)
```
