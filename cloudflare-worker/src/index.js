const VERSION = '14A.1.0';
const OAUTH_TOKEN_URL_PRODUCTION = 'https://api.ebay.com/identity/v1/oauth2/token';
const OAUTH_TOKEN_URL_SANDBOX = 'https://api.sandbox.ebay.com/identity/v1/oauth2/token';
const DEFAULT_EBAY_ENVIRONMENT = 'sandbox';
const EXCHANGE_GRANT_TTL_SECONDS = 180;

const consumedExchangeGrants = new Map();

const JSON_HEADERS = {
  'content-type': 'application/json; charset=utf-8',
  'cache-control': 'no-store',
};

const TEXT_HEADERS = {
  'content-type': 'text/plain; charset=utf-8',
  'cache-control': 'no-store',
};

const HTML_HEADERS = {
  'content-type': 'text/html; charset=utf-8',
  'cache-control': 'no-store',
};

export default {
  async fetch(request, env, ctx) {
    try {
      const url = new URL(request.url);
      const path = normalizePath(url.pathname);
      const method = request.method.toUpperCase();

      if (method === 'GET' && path === '/') {
        return text('OPS Nexus Cloud Service Running');
      }

      if (method === 'GET' && path === '/health') {
        return json({
          status: 'ok',
          version: VERSION,
          timestamp: new Date().toISOString(),
        });
      }

      if (method === 'GET' && path === '/oauth/callback') {
        return await handleOAuthCallback(request, env);
      }

      if (method === 'GET' && path === '/oauth/exchange') {
        return await handleOAuthExchange(request, env);
      }

      if (method === 'GET' && path === '/ebay/account-deletion') {
        return await handleDeletionChallenge(request, env);
      }

      if (method === 'POST' && path === '/ebay/account-deletion') {
        return await handleDeletionNotification(request, env);
      }

      return text('Not Found', 404);
    } catch (error) {
      logError('unhandled_error', error);
      return json(
        {
          status: 'error',
          message: 'Internal server error',
          timestamp: new Date().toISOString(),
        },
        500,
      );
    }
  },
};

function validateRequiredSecrets(env, required) {
  if (!Array.isArray(required) || required.length === 0) {
    throw new Error('No required secrets specified for validation.');
  }

  for (const key of required) {
    if (!env[key] || String(env[key]).trim() === '') {
      throw new Error(`Missing required secret: ${key}`);
    }
  }
}

async function handleOAuthCallback(request, env) {
  const callbackUrl = new URL(request.url);
  console.log('OAUTH CALLBACK HIT');
  console.log(request.url);
  console.log(callbackUrl.pathname);
  console.log([...callbackUrl.searchParams.keys()]);
  console.log(Boolean((callbackUrl.searchParams.get('code') || '').trim()));
  console.log(Boolean((callbackUrl.searchParams.get('state') || '').trim()));

  validateRequiredSecrets(env, ['EBAY_CLIENT_ID', 'EBAY_CLIENT_SECRET']);

  const url = new URL(request.url);
  console.log('[OAuth Callback] Entered handleOAuthCallback');
  console.log(`[OAuth Callback] Request URL: ${request.url}`);

  if (!isTrustedOrigin(request, 'oauth')) {
    logWarn('oauth_origin_rejected', {
      origin: request.headers.get('origin'),
      referer: request.headers.get('referer'),
      ipHash: hashIpForLog(request),
    });
    return text('Forbidden', 403);
  }

  const code = (url.searchParams.get('code') || '').trim();
  const state = (url.searchParams.get('state') || '').trim();
  const error = (url.searchParams.get('error') || '').trim();
  console.log(`[OAuth Callback] Query has code: ${Boolean(code)}`);
  console.log(`[OAuth Callback] Query has state: ${Boolean(state)}`);
  console.log(`[OAuth Callback] Query has error: ${Boolean(error)}`);
  const stateCheck = await validateOAuthState(state, env);
  console.log(`[OAuth Callback] validateOAuthState result: ${JSON.stringify(stateCheck)}`);

  if (error) {
    logWarn('oauth_callback_error', {
      error,
      statePresent: Boolean(state),
      ipHash: hashIpForLog(request),
    });

    return html(renderOAuthResultPage(false, {
      title: 'OAuth callback rejected',
      detail: `eBay returned an error: ${escapeHtml(error)}`,
    }), 400);
  }

  if (!stateCheck.ok || !code) {
    logWarn('oauth_callback_invalid_query', {
      codePresent: Boolean(code),
      statePresent: Boolean(state),
      stateSigned: stateCheck.signed,
      stateReason: stateCheck.reason,
      ipHash: hashIpForLog(request),
    });
    return html(renderOAuthResultPage(false, {
      title: 'OAuth callback rejected',
      detail: 'Missing or invalid code/state values.',
    }), 400);
  }

  logInfo('oauth_callback_received', {
    codeLength: code.length,
    stateLength: state.length,
    stateSigned: stateCheck.signed,
    ipHash: hashIpForLog(request),
  });

  let tokenPayload;
  try {
    console.log('[OAuth Callback] Calling exchangeAuthorizationCode');
    tokenPayload = await exchangeAuthorizationCode(code, request, env);
    console.log('[OAuth Callback] exchangeAuthorizationCode succeeded');
  } catch (error) {
    logWarn('oauth_token_exchange_failed', {
      reason: error instanceof Error ? error.message : String(error),
      ipHash: hashIpForLog(request),
    });

    return html(renderOAuthResultPage(false, {
      title: 'OAuth token exchange failed',
      detail: 'Authorization code was valid, but token exchange with eBay failed.',
      action: 'Try Sign In again. If this keeps failing, verify OAuth redirect URI and client credentials.',
    }), 502);
  }

  console.log('[OAuth Callback] Calling deliverOAuthTokens');
  const handoffResult = await deliverOAuthTokens(tokenPayload, stateCheck, request, env);
  console.log(`[OAuth Callback] handoffResult: ${JSON.stringify(handoffResult)}`);
  if (!handoffResult.ok) {
    logWarn('oauth_token_handoff_failed', {
      mode: handoffResult.mode,
      reason: handoffResult.reason,
      ipHash: hashIpForLog(request),
    });

    return html(renderOAuthResultPage(false, {
      title: 'OAuth handoff failed',
      detail: handoffResult.userMessage,
      action: handoffResult.actionMessage,
      exchangeUrl: handoffResult.exchangeUrl,
    }), 502);
  }

  const successDetail = handoffResult.mode === 'callback'
    ? 'OAuth token exchange succeeded and tokens were securely delivered to OPS Nexus Desktop.'
    : handoffResult.mode === 'browser_callback'
      ? 'OAuth token exchange succeeded. Finalizing secure transfer to OPS Nexus Desktop on this device...'
      : 'OAuth token exchange succeeded. Use the temporary secure exchange link in OPS Nexus Desktop.';

  console.log(`[OAuth Callback] FINAL exchangeUrl sent to browser: ${safeString(handoffResult.exchangeUrl)}`);

  return html(renderOAuthResultPage(true, {
    title: 'OAuth callback received',
    detail: successDetail,
    statePreview: maskValue(state),
    exchangeUrl: handoffResult.exchangeUrl,
    bridgeConfig: handoffResult.mode === 'browser_callback'
      ? {
          callbackUrl: handoffResult.callbackUrl,
          exchangeUrl: handoffResult.exchangeUrl,
        }
      : undefined,
  }));
}

async function handleOAuthExchange(request, env) {
  const url = new URL(request.url);
  const grant = (url.searchParams.get('grant') || '').trim();

  if (!grant) {
    return json({ message: 'Missing grant' }, 400);
  }

  const digest = await sha256Hex(grant);
  pruneConsumedExchangeGrants();
  if (consumedExchangeGrants.has(digest)) {
    return json({ message: 'Grant already consumed' }, 410);
  }

  let decrypted;
  try {
    decrypted = await decryptExchangeGrant(grant, env);
  } catch (error) {
    logWarn('oauth_exchange_invalid_grant', {
      reason: error instanceof Error ? error.message : String(error),
      ipHash: hashIpForLog(request),
    });
    return json({ message: 'Invalid grant' }, 400);
  }

  const nowMs = Date.now();
  if (!decrypted?.exp || nowMs >= Number(decrypted.exp) * 1000) {
    return json({ message: 'Grant expired' }, 410);
  }

  consumedExchangeGrants.set(digest, nowMs + (EXCHANGE_GRANT_TTL_SECONDS * 1000));

  return json({
    provider: 'ebay',
    access_token: safeString(decrypted.access_token),
    refresh_token: safeString(decrypted.refresh_token),
    expires_in: Number(decrypted.expires_in || 0),
    refresh_token_expires_in: Number(decrypted.refresh_token_expires_in || 0),
    token_type: safeString(decrypted.token_type),
    scope: safeString(decrypted.scope),
  });
}

async function handleDeletionChallenge(request, env) {
  validateRequiredSecrets(env, ['EBAY_VERIFICATION_TOKEN']);

  if (!isTrustedOrigin(request, 'deletion')) {
    logWarn('deletion_challenge_origin_rejected', {
      origin: request.headers.get('origin'),
      referer: request.headers.get('referer'),
      ipHash: hashIpForLog(request),
    });
    return text('Forbidden', 403);
  }

  const url = new URL(request.url);
  const challengeCode = (url.searchParams.get('challenge_code') || '').trim();

  if (!isValidChallengeCode(challengeCode)) {
    logWarn('deletion_challenge_invalid', {
      challengePresent: Boolean(challengeCode),
      ipHash: hashIpForLog(request),
    });
    return json({ message: 'Missing or invalid challenge_code' }, 400);
  }

  const endpoint = `${url.origin}/ebay/account-deletion`;
  const challengeResponse = await sha256Hex(
    `${challengeCode}${env.EBAY_VERIFICATION_TOKEN}${endpoint}`,
  );

  logInfo('deletion_challenge_validated', {
    challengeLength: challengeCode.length,
    endpoint,
    ipHash: hashIpForLog(request),
  });

  return json({ challengeResponse });
}

async function handleDeletionNotification(request, env) {
  validateRequiredSecrets(env, ['EBAY_VERIFICATION_TOKEN']);

  if (!isTrustedOrigin(request, 'deletion')) {
    logWarn('deletion_notification_origin_rejected', {
      origin: request.headers.get('origin'),
      referer: request.headers.get('referer'),
      ipHash: hashIpForLog(request),
    });
    return text('Forbidden', 403);
  }

  const tokenCandidate = readVerificationToken(request);
  if (!tokenCandidate || tokenCandidate !== env.EBAY_VERIFICATION_TOKEN) {
    logWarn('deletion_notification_token_rejected', {
      tokenPresent: Boolean(tokenCandidate),
      signaturePresent: Boolean(request.headers.get('x-ebay-signature')),
      ipHash: hashIpForLog(request),
    });
    return text('Unauthorized', 401);
  }

  const signature = (request.headers.get('x-ebay-signature') || '').trim();
  if (!signature) {
    logWarn('deletion_notification_missing_signature', {
      ipHash: hashIpForLog(request),
    });
    return text('Precondition Failed', 412);
  }

  let payload;
  try {
    payload = await request.json();
  } catch (error) {
    logWarn('deletion_notification_invalid_json', {
      ipHash: hashIpForLog(request),
      reason: error instanceof Error ? error.message : String(error),
    });
    return json({ message: 'Invalid JSON payload' }, 400);
  }

  const safeLog = summarizeDeletionPayload(payload);
  logInfo('deletion_notification_received', {
    ...safeLog,
    signatureLength: signature.length,
    ipHash: hashIpForLog(request),
  });

  return text('OK', 200);
}

function summarizeDeletionPayload(payload) {
  const metadata = payload?.metadata || {};
  const notification = payload?.notification || {};

  return {
    topic: safeString(metadata.topic),
    schemaVersion: safeString(metadata.schemaVersion),
    notificationIdSuffix: tail8(safeString(notification.notificationId)),
    eventDate: safeString(notification.eventDate),
    publishDate: safeString(notification.publishDate),
    publishAttemptCount: Number(notification.publishAttemptCount || 0),
  };
}

function readVerificationToken(request) {
  const url = new URL(request.url);

  const fromHeader = (request.headers.get('x-ebay-verification-token') || '').trim();
  if (fromHeader) {
    return fromHeader;
  }

  const fromQuery = (url.searchParams.get('verification_token') || '').trim();
  if (fromQuery) {
    return fromQuery;
  }

  return '';
}

function isTrustedOrigin(request, flow) {
  const originHeader = request.headers.get('origin');
  const refererHeader = request.headers.get('referer');

  if (!originHeader && !refererHeader) {
    if (flow === 'deletion') {
      return Boolean(request.headers.get('x-ebay-signature'));
    }
    return true;
  }

  const hosts = [];

  if (originHeader) {
    try {
      hosts.push(new URL(originHeader).hostname.toLowerCase());
    } catch {
      return false;
    }
  }

  if (refererHeader) {
    try {
      hosts.push(new URL(refererHeader).hostname.toLowerCase());
    } catch {
      return false;
    }
  }

  return hosts.every(isTrustedEbayHost);
}

function isTrustedEbayHost(hostname) {
  return hostname.endsWith('.ebay.com') || hostname === 'ebay.com' || hostname.endsWith('.ebaystatic.com');
}

function isValidOAuthCode(code) {
  return /^[A-Za-z0-9._~\-]{8,2048}$/.test(code);
}

function isValidState(state) {
  return /^[A-Za-z0-9._~\-]{8,256}$/.test(state);
}

function isValidDesktopCallbackUrl(value) {
  try {
    const parsed = new URL(value);
    const host = parsed.hostname.toLowerCase();
    const isLocalHost = host === 'localhost' || host === '127.0.0.1' || host === '::1';
    if (parsed.protocol === 'https:') {
      return true;
    }
    return parsed.protocol === 'http:' && isLocalHost;
  } catch {
    return false;
  }
}

async function validateOAuthState(state, env) {
  if (!isValidState(state)) {
    return { ok: false, reason: 'state_format_invalid', signed: false };
  }

  if (!state.startsWith('v1.')) {
    return { ok: false, reason: 'state_unsigned', signed: false };
  }

  const parts = state.split('.');
  if (parts.length !== 3) {
    return { ok: false, reason: 'state_signed_format_invalid', signed: true };
  }

  const stateSecret = safeString(env.OPS_NEXUS_STATE_SECRET).trim();
  const stateSecretExists = Boolean(stateSecret);
  const stateSecretLength = stateSecret.length;
  const stateSecretHead = stateSecretLength ? stateSecret.slice(0, 8) : '';
  const stateSecretTail = stateSecretLength ? stateSecret.slice(-8) : '';
  console.log(`[OAuth State Worker] OPS_NEXUS_STATE_SECRET exists: ${stateSecretExists}`);
  console.log(`[OAuth State Worker] OPS_NEXUS_STATE_SECRET length: ${stateSecretLength}`);
  console.log(
    stateSecretExists
      ? `[OAuth State Worker] OPS_NEXUS_STATE_SECRET preview: ${stateSecretHead}...${stateSecretTail}`
      : '[OAuth State Worker] OPS_NEXUS_STATE_SECRET preview: (missing)',
  );
  if (!stateSecret) {
    return { ok: false, reason: 'state_secret_missing', signed: true };
  }

  const payloadB64 = parts[1];
  const sigB64 = parts[2];
  const signedData = `v1.${payloadB64}`;
  console.log(`[OAuth State Worker] payloadB64: ${payloadB64}`);
  console.log(`[OAuth State Worker] signedData: ${signedData}`);
  console.log(`[OAuth State Worker] received sigB64: ${sigB64}`);
  const isSignatureValid = await verifyHmacSha256(stateSecret, signedData, sigB64);
  if (!isSignatureValid) {
    return { ok: false, reason: 'state_signature_invalid', signed: true };
  }

  let payload;
  try {
    payload = JSON.parse(decodeBase64UrlToString(payloadB64));
  } catch {
    return { ok: false, reason: 'state_payload_invalid', signed: true };
  }

  const now = Math.floor(Date.now() / 1000);
  const iat = Number(payload?.iat || 0);
  const exp = Number(payload?.exp || 0);
  if (!iat || !exp || exp <= now || (exp - iat) > 900) {
    return { ok: false, reason: 'state_window_invalid', signed: true };
  }

  const callbackUrl = safeString(payload?.desktop_callback_url).trim();
  if (callbackUrl && !isValidDesktopCallbackUrl(callbackUrl)) {
    return { ok: false, reason: 'state_callback_invalid', signed: true };
  }

  return {
    ok: true,
    reason: 'state_signed_valid',
    signed: true,
    desktopCallbackUrl: callbackUrl,
  };
}

async function exchangeAuthorizationCode(code, request, env) {
  const clientId = safeString(env.EBAY_CLIENT_ID).trim();
  const clientSecret = safeString(env.EBAY_CLIENT_SECRET).trim();
  const redirectUri = safeString(env.EBAY_REDIRECT_URI).trim() || `${new URL(request.url).origin}/oauth/callback`;
  const ebayEnvironment = safeString(env.EBAY_ENVIRONMENT).trim().toLowerCase() || DEFAULT_EBAY_ENVIRONMENT;
  const isSandbox = ebayEnvironment === 'sandbox';
  const tokenUrl = isSandbox ? OAUTH_TOKEN_URL_SANDBOX : OAUTH_TOKEN_URL_PRODUCTION;
  console.log('[Token Exchange] Starting exchangeAuthorizationCode');
  console.log(`[Token Exchange] Environment: ${ebayEnvironment}`);
  console.log(`[Token Exchange] Client ID: ${clientId}`);
  console.log(`[Token Exchange] Redirect URI: ${redirectUri}`);
  console.log(`[Token Exchange] eBay token endpoint: ${tokenUrl}`);

  const credentials = toBase64(`${clientId}:${clientSecret}`);
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    code,
    redirect_uri: redirectUri,
  });
  console.log(
    `[Token Exchange] POST body (safe): ${JSON.stringify({ grant_type: 'authorization_code', codeLength: code.length, redirect_uri: redirectUri })}`,
  );

  const response = await fetch(tokenUrl, {
    method: 'POST',
    headers: {
      authorization: `Basic ${credentials}`,
      'content-type': 'application/x-www-form-urlencoded',
      accept: 'application/json',
    },
    body: body.toString(),
  });
  console.log(`[Token Exchange] HTTP status from eBay: ${response.status}`);
  const responseText = await response.text();
  const safeResponseText = redactSensitiveOAuthResponseText(responseText);
  console.log(`[Token Exchange] Response body (raw): ${safeResponseText}`);

  if (!response.ok) {
    throw new Error(`eBay token endpoint error (${response.status}): ${safeResponseText.slice(0, 180)}`);
  }

  const tokenPayload = JSON.parse(responseText);
  const accessToken = safeString(tokenPayload?.access_token);
  const refreshToken = safeString(tokenPayload?.refresh_token);
  const expiresIn = Number(tokenPayload?.expires_in || 0);
  const refreshExpiresIn = Number(tokenPayload?.refresh_token_expires_in || 0);
  console.log(
    `[Token Exchange] Parsed token fields (lengths): ${JSON.stringify({ access_token_length: accessToken.length, refresh_token_length: refreshToken.length, token_type_length: safeString(tokenPayload?.token_type).length, scope_length: safeString(tokenPayload?.scope).length, expires_in: expiresIn, refresh_token_expires_in: refreshExpiresIn })}`,
  );

  if (!accessToken || !refreshToken || !expiresIn || !refreshExpiresIn) {
    throw new Error('eBay token response is missing required fields.');
  }

  return {
    access_token: accessToken,
    refresh_token: refreshToken,
    expires_in: expiresIn,
    refresh_token_expires_in: refreshExpiresIn,
    token_type: safeString(tokenPayload?.token_type),
    scope: safeString(tokenPayload?.scope),
  };
}

async function deliverOAuthTokens(tokenPayload, stateCheck, request, env) {
  const callbackUrl = (stateCheck?.desktopCallbackUrl || safeString(env.OPS_NEXUS_DESKTOP_CALLBACK_URL)).trim();
  console.log('[Desktop Handoff] Starting deliverOAuthTokens');
  console.log(`[Desktop Handoff] callbackUrl: ${callbackUrl}`);
  console.log(`[Desktop Handoff] callbackUrl localhost: ${isLocalhostCallbackUrl(callbackUrl)}`);

  if (callbackUrl) {
    if (!isValidDesktopCallbackUrl(callbackUrl)) {
      console.log('[Desktop Handoff] Early return: desktop_callback_invalid');
      return {
        ok: false,
        mode: 'callback',
        reason: 'desktop_callback_invalid',
        userMessage: 'Desktop callback URL is invalid. It must be HTTPS, or localhost over HTTP.',
        actionMessage: 'Update OPS_NEXUS_DESKTOP_CALLBACK_URL or the signed state payload.',
      };
    }

    if (isLocalhostCallbackUrl(callbackUrl)) {
      console.log('[Desktop Handoff] Mode chosen: browser_callback');
      const exchange = await createExchangeGrantUrl(tokenPayload, request, env);
      if (!exchange.ok) {
        console.log(`[Desktop Handoff] Early return from exchange setup: ${safeString(exchange.reason)}`);
        return exchange;
      }
      console.log(`[Desktop Handoff] exchangeUrl: ${safeString(exchange.exchangeUrl)}`);

      return {
        ok: true,
        mode: 'browser_callback',
        exchangeUrl: exchange.exchangeUrl,
        callbackUrl,
      };
    }

    const callbackHeaders = {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
    };

    const callbackBearer = safeString(env.OPS_NEXUS_DESKTOP_CALLBACK_BEARER).trim();
    if (callbackBearer) {
      callbackHeaders.authorization = `Bearer ${callbackBearer}`;
    }

    try {
      const callbackResponse = await fetch(callbackUrl, {
        method: 'POST',
        headers: callbackHeaders,
        body: JSON.stringify({
          provider: 'ebay',
          status: 'ok',
          timestamp: new Date().toISOString(),
          ...tokenPayload,
        }),
      });
      console.log(`[Desktop Handoff] callback HTTP status: ${callbackResponse.status}`);

      if (callbackResponse.ok) {
        console.log('[Desktop Handoff] Mode chosen: callback');
        return {
          ok: true,
          mode: 'callback',
          callbackUrl,
        };
      }

      const callbackResponseHeaders = Object.fromEntries(callbackResponse.headers.entries());
      const callbackResponseBody = await callbackResponse.text();
      console.log(`[Desktop Handoff] callback response headers: ${JSON.stringify(callbackResponseHeaders)}`);
      console.log(`[Desktop Handoff] callback response body: ${callbackResponseBody}`);
      console.log(`[Desktop Handoff] callback failed, falling back to exchange: desktop_callback_http_${callbackResponse.status}`);
    } catch (error) {
      console.log(`[Desktop Handoff] callback failed, falling back to exchange: ${error instanceof Error ? error.message : String(error)}`);
    }

    const exchange = await createExchangeGrantUrl(tokenPayload, request, env);
    if (!exchange.ok) {
      return {
        ...exchange,
        userMessage: 'OAuth tokens were issued, but delivery to the desktop callback failed.',
        actionMessage: 'Ensure the desktop callback receiver is running and reachable, or set OPS_NEXUS_EXCHANGE_SECRET for manual exchange.',
      };
    }

    return exchange;
  }

  return createExchangeGrantUrl(tokenPayload, request, env);
}

async function createExchangeGrantUrl(tokenPayload, request, env) {
  const exchangeSecret = safeString(env.OPS_NEXUS_EXCHANGE_SECRET).trim();
  if (!exchangeSecret) {
    console.log('[Desktop Handoff] Early return: exchange_secret_missing');
    return {
      ok: false,
      mode: 'exchange',
      reason: 'exchange_secret_missing',
      userMessage: 'No desktop callback configured and OPS_NEXUS_EXCHANGE_SECRET is missing.',
      actionMessage: 'Set OPS_NEXUS_DESKTOP_CALLBACK_URL or OPS_NEXUS_EXCHANGE_SECRET.',
    };
  }

  const now = Math.floor(Date.now() / 1000);
  const grantPayload = {
    ...tokenPayload,
    iat: now,
    exp: now + EXCHANGE_GRANT_TTL_SECONDS,
    nonce: generateNonce(16),
  };

  const grant = await encryptExchangeGrant(grantPayload, exchangeSecret);
  const exchangeUrl = `${new URL(request.url).origin}/oauth/exchange?grant=${encodeURIComponent(grant)}`;
  console.log(`[Desktop Handoff] exchange grant: ${grant}`);
  console.log(`[Desktop Handoff] exchange grant length: ${grant.length}`);
  console.log(`[Desktop Handoff] exchangeUrl exact: ${exchangeUrl}`);
  console.log('[Desktop Handoff] Mode chosen: exchange');
  console.log(`[Desktop Handoff] exchangeUrl: ${exchangeUrl}`);

  return {
    ok: true,
    mode: 'exchange',
    exchangeUrl,
  };
}

function isLocalhostCallbackUrl(value) {
  try {
    const parsed = new URL(value);
    const host = parsed.hostname.toLowerCase();
    return parsed.protocol === 'http:' && (host === 'localhost' || host === '127.0.0.1' || host === '::1');
  } catch {
    return false;
  }
}

function pruneConsumedExchangeGrants() {
  const now = Date.now();
  for (const [key, expiryMs] of consumedExchangeGrants.entries()) {
    if (!expiryMs || expiryMs <= now) {
      consumedExchangeGrants.delete(key);
    }
  }
}

async function encryptExchangeGrant(payload, secret) {
  const key = await importAesGcmKey(secret);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const plaintext = new TextEncoder().encode(JSON.stringify(payload));
  const cipher = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, plaintext);
  return `v1.${encodeBase64Url(iv)}.${encodeBase64Url(new Uint8Array(cipher))}`;
}

async function decryptExchangeGrant(grant, env) {
  const exchangeSecret = safeString(env.OPS_NEXUS_EXCHANGE_SECRET).trim();
  if (!exchangeSecret) {
    throw new Error('OPS_NEXUS_EXCHANGE_SECRET missing');
  }

  const parts = grant.split('.');
  if (parts.length !== 3 || parts[0] !== 'v1') {
    throw new Error('Invalid grant format');
  }

  const key = await importAesGcmKey(exchangeSecret);
  const iv = decodeBase64Url(parts[1]);
  const cipherBytes = decodeBase64Url(parts[2]);
  const plainBuffer = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, cipherBytes);
  const plainText = new TextDecoder().decode(plainBuffer);
  return JSON.parse(plainText);
}

async function importAesGcmKey(secret) {
  const keyMaterial = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(secret));
  return crypto.subtle.importKey('raw', keyMaterial, { name: 'AES-GCM' }, false, ['encrypt', 'decrypt']);
}

async function verifyHmacSha256(secret, value, signatureB64Url) {
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const expected = new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(value)));
  const actual = decodeBase64Url(signatureB64Url);
  return timingSafeEqual(expected, actual);
}

function timingSafeEqual(a, b) {
  if (!(a instanceof Uint8Array) || !(b instanceof Uint8Array)) {
    return false;
  }
  if (a.length !== b.length) {
    return false;
  }

  let diff = 0;
  for (let i = 0; i < a.length; i += 1) {
    diff |= a[i] ^ b[i];
  }
  return diff === 0;
}

function encodeBase64Url(bytes) {
  let binary = '';
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '');
}

function decodeBase64Url(value) {
  const normalized = value.replaceAll('-', '+').replaceAll('_', '/');
  const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function decodeBase64UrlToString(value) {
  return new TextDecoder().decode(decodeBase64Url(value));
}

function toBase64(value) {
  const bytes = new TextEncoder().encode(value);
  let binary = '';
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

function generateNonce(length) {
  const charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  const bytes = crypto.getRandomValues(new Uint8Array(length));
  let result = '';
  for (let i = 0; i < bytes.length; i += 1) {
    result += charset[bytes[i] % charset.length];
  }
  return result;
}

function isValidChallengeCode(code) {
  return /^[A-Za-z0-9._~\-]{8,512}$/.test(code);
}

async function sha256Hex(value) {
  const input = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest('SHA-256', input);
  const bytes = new Uint8Array(digest);
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function hashIpForLog(request) {
  const ip = request.headers.get('cf-connecting-ip') || '';
  if (!ip) {
    return '';
  }
  return maskValue(ip);
}

function safeString(value) {
  if (typeof value === 'string') {
    return value;
  }
  if (value === null || value === undefined) {
    return '';
  }
  return String(value);
}

function redactSensitiveOAuthResponseText(value) {
  const raw = safeString(value);

  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object') {
      const sanitized = { ...parsed };
      if (Object.prototype.hasOwnProperty.call(sanitized, 'access_token')) {
        sanitized.access_token = '[redacted]';
      }
      if (Object.prototype.hasOwnProperty.call(sanitized, 'refresh_token')) {
        sanitized.refresh_token = '[redacted]';
      }
      return JSON.stringify(sanitized);
    }
  } catch {
    // Fall back to regex-based masking for non-JSON payloads.
  }

  return raw
    .replace(/("access_token"\s*:\s*")[^"]*(")/gi, '$1[redacted]$2')
    .replace(/("refresh_token"\s*:\s*")[^"]*(")/gi, '$1[redacted]$2');
}

function tail8(value) {
  if (!value) {
    return '';
  }
  return value.slice(-8);
}

function maskValue(value) {
  if (!value) {
    return '';
  }
  if (value.length <= 8) {
    return '***';
  }
  return `${value.slice(0, 4)}...${value.slice(-4)}`;
}

function normalizePath(pathname) {
  if (!pathname || pathname === '/') {
    return '/';
  }
  return pathname.endsWith('/') ? pathname.slice(0, -1) : pathname;
}

function renderOAuthResultPage(ok, details) {
  const status = ok ? 'Success' : 'Failed';
  const color = ok ? '#0a7f3f' : '#a30d11';
  const stateLine = details.statePreview
    ? `<p><strong>State:</strong> ${escapeHtml(details.statePreview)}</p>`
    : '';
  const actionLine = details.action
    ? `<p><strong>Action:</strong> ${escapeHtml(details.action)}</p>`
    : '';
  const exchangeLine = details.exchangeUrl
    ? `<p><strong>Exchange URL:</strong> <a href="${escapeHtml(details.exchangeUrl)}">Open secure token exchange</a></p>`
    : '';
  const bridgeStatusLine = details.bridgeConfig
    ? '<p id="bridge-status"><strong>Desktop transfer:</strong> Waiting...</p>'
    : '';
  const bridgeScript = details.bridgeConfig
    ? `<script>
      (async () => {
        const statusEl = document.getElementById('bridge-status');
        const exchangeUrl = ${JSON.stringify(details.bridgeConfig.exchangeUrl)};
        const callbackUrl = ${JSON.stringify(details.bridgeConfig.callbackUrl)};
        const callbackPayload = {
          provider: 'ebay',
          exchange_url: exchangeUrl,
        };
        const callbackRequestBody = JSON.stringify(callbackPayload);

        try {
          console.log('[Desktop Bridge] Browser POST exchange_url:', exchangeUrl);
          console.log('[Desktop Bridge] callbackUrl:', callbackUrl);
          console.log('[Desktop Bridge] POST payload:', callbackPayload);
          console.log('FETCH URL:', callbackUrl);
          console.log('FETCH BODY:', callbackRequestBody);
          console.log('[Desktop Bridge] Starting localhost POST');
          const callbackResponse = await fetch(callbackUrl, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: callbackRequestBody,
          });
          const callbackResponseHeaders = Object.fromEntries(callbackResponse.headers.entries());
          const callbackResponseBody = await callbackResponse.text();
          console.log('[Desktop Bridge] localhost POST completed');
          console.log('FETCH STATUS:', callbackResponse.status);
          console.log('FETCH TEXT:', callbackResponseBody);
          console.log('[Desktop Bridge] callback HTTP status:', callbackResponse.status);
          console.log('[Desktop Bridge] callback response headers:', callbackResponseHeaders);
          console.log('[Desktop Bridge] callback response body:', callbackResponseBody);
          if (!callbackResponse.ok) {
            throw new Error('Desktop callback rejected token payload.');
          }

          if (statusEl) {
            statusEl.innerHTML = '<strong>Desktop transfer:</strong> Completed.';
          }
        } catch (err) {
          console.log('[Desktop Bridge] catch block entered');
          console.log('[Desktop Bridge] localhost POST failed');
          console.log('[Desktop Bridge] error name:', err && err.name ? err.name : '(unknown)');
          console.log('[Desktop Bridge] error message:', err && err.message ? err.message : String(err));
          console.log('[Desktop Bridge] error stack:', err && err.stack ? err.stack : '(no stack)');
          if (statusEl) {
            statusEl.innerHTML = '<strong>Desktop transfer:</strong> Failed. Keep OPS Nexus running and use the exchange link manually.';
          }
        }
      })();
    </script>`
    : '';

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>OPS Nexus OAuth Callback</title>
    <style>
      body { font-family: Arial, sans-serif; background: #f5f7fb; color: #111827; margin: 0; }
      main { max-width: 640px; margin: 48px auto; background: #fff; border-radius: 12px; padding: 24px; box-shadow: 0 8px 24px rgba(17,24,39,.08); }
      h1 { margin-top: 0; color: ${color}; }
      p { line-height: 1.5; }
      .status { font-weight: 700; color: ${color}; }
    </style>
  </head>
  <body>
    <main>
      <h1>OPS Nexus Cloud Service</h1>
      <p class="status">OAuth ${status}</p>
      <p><strong>${escapeHtml(details.title || '')}</strong></p>
      <p>${escapeHtml(details.detail || '')}</p>
      ${stateLine}
      ${actionLine}
      ${exchangeLine}
      ${bridgeStatusLine}
      <p>You can return to OPS Nexus.</p>
    </main>
    ${bridgeScript}
  </body>
</html>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: JSON_HEADERS,
  });
}

function text(body, status = 200) {
  return new Response(body, {
    status,
    headers: TEXT_HEADERS,
  });
}

function html(body, status = 200) {
  return new Response(body, {
    status,
    headers: HTML_HEADERS,
  });
}

function logInfo(event, data = {}) {
  console.log(JSON.stringify({ level: 'info', event, ...data }));
}

function logWarn(event, data = {}) {
  console.warn(JSON.stringify({ level: 'warn', event, ...data }));
}

function logError(event, error) {
  console.error(
    JSON.stringify({
      level: 'error',
      event,
      message: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : undefined,
    }),
  );
}
