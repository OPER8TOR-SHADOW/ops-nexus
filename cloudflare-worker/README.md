# OPS Nexus Cloud Service (Phase 14A.1)

Minimal Cloudflare Worker for eBay Production OAuth callback and Marketplace Account Deletion compliance.

This worker is intentionally **not** an OPS Nexus backend.

## Endpoints

### `GET /`
Returns plain text:

`OPS Nexus Cloud Service Running`

### `GET /health`
Returns JSON:

- `status`
- `version`
- `timestamp`

### `GET /oauth/callback`
Receives eBay OAuth redirect query params.

- Validates `code` and `state`
- Performs origin checks when `Origin`/`Referer` are present
- Logs callback metadata only (no token/code storage)
- Returns a simple success/failure HTML page

### `GET /ebay/account-deletion`
Handles eBay subscription challenge flow.

- Reads `challenge_code` query param
- Generates `challengeResponse` as SHA-256 of:
  - `challengeCode + verificationToken + endpoint`
- Returns JSON with `challengeResponse`

### `POST /ebay/account-deletion`
Receives account deletion notifications.

- Validates request origin/signature presence
- Validates verification token (header or query)
- Acknowledges with HTTP `200 OK`
- Logs safe metadata only
- Does not persist personal data

## Required Secrets

Set these as Cloudflare Worker secrets (never hardcode):

- `EBAY_CLIENT_ID`
- `EBAY_CLIENT_SECRET`
- `EBAY_VERIFICATION_TOKEN`

## Local Development

1. Install Wrangler globally or in your preferred toolchain.
2. From this folder, copy `.dev.vars.example` to `.dev.vars`.
3. Fill `.dev.vars` with real values.
4. Run:

```bash
wrangler dev
```

## Deployment (Production)

From this folder:

```bash
wrangler secret put EBAY_CLIENT_ID
wrangler secret put EBAY_CLIENT_SECRET
wrangler secret put EBAY_VERIFICATION_TOKEN
wrangler deploy
```

Wrangler prints the worker URL, typically:

- `https://ops-nexus-cloud-service.<account>.workers.dev`

## Verification (curl examples)

Replace `BASE_URL` with your worker URL.

### 1) Health

```bash
curl -i "$BASE_URL/health"
```

Expected: `200`, JSON with `status`, `version`, `timestamp`.

### 2) OAuth callback

```bash
curl -i "$BASE_URL/oauth/callback?code=abcDEF1234token&state=opsnexusstate01"
```

Expected: `200`, HTML page confirming callback validated.

### 3) Account deletion challenge (GET)

```bash
curl -i "$BASE_URL/ebay/account-deletion?challenge_code=challenge12345678"
```

Expected: `200`, JSON with `challengeResponse`.

### 4) Account deletion notification (POST)

```bash
curl -i -X POST "$BASE_URL/ebay/account-deletion?verification_token=<YOUR_TOKEN>" \
  -H "content-type: application/json" \
  -H "x-ebay-signature: sample-signature" \
  -d '{
    "metadata": {"topic": "MARKETPLACE_ACCOUNT_DELETION", "schemaVersion": "1.0"},
    "notification": {
      "notificationId": "12345678-1234-1234-1234-1234567890ab",
      "eventDate": "2026-07-28T12:00:00.000Z",
      "publishDate": "2026-07-28T12:00:01.000Z",
      "publishAttemptCount": 1,
      "data": {"username": "masked", "userId": "masked", "eiasToken": "masked"}
    }
  }'
```

Expected: `200 OK`.

## Logging

Structured logs include:

- OAuth callback events
- Deletion challenge + notifications
- Errors and warnings

Logs are privacy-aware (metadata only, masked fields where possible).

## Health Report Checklist

- `GET /` responds with required running message
- `GET /health` responds with status/version/timestamp
- `GET /oauth/callback` validates and returns HTML confirmation
- `GET /ebay/account-deletion` supports challenge handshake
- `POST /ebay/account-deletion` validates and acknowledges notifications
- All secrets come from Cloudflare Secrets
- No personal data persistence
