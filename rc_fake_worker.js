
// ═══════════════════════════════════════════════════════════════
//  Fake RevenueCat API — Cloudflare Worker
//  Deploy: workers.dev (free tier, always-on, no VPS needed)
//  Handles: /v1/subscribers/*, /v1/receipts, /v1/offerings, /v2/subscribers/*
// ═══════════════════════════════════════════════════════════════

const START  = "2024-01-01T00:00:00Z";
const EXPIRE = "2099-12-31T23:59:59Z";

const PRODUCTS = [
  "com.locket.premium.yearly",
  "com.locket.premium.monthly",
  "Gold",
  "gold",
  "pro",
  "premium",
];

function makeSubscription() {
  return {
    is_sandbox:                  false,
    ownership_type:              "PURCHASED",
    period_type:                 "normal",
    purchase_date:               START,
    original_purchase_date:      START,
    expires_date:                EXPIRE,
    latest_expires_date:         EXPIRE,
    store:                       "app_store",
    grace_period_expires_date:   null,
    unsubscribe_detected_at:     null,
    billing_issues_detected_at:  null,
    refund_at:                   null,
    is_trial_period:             false,
  };
}

function makeEntitlement(pid) {
  return {
    ...makeSubscription(),
    product_identifier:      pid,
    identifier:              pid,
    active:                  true,
    is_active:               true,
    renewal_state:           "subscribed",
    will_renew:              true,
  };
}

function buildSubscriberBody(userId) {
  const subs  = {};
  const ents  = {};
  PRODUCTS.forEach(p => {
    subs[p] = makeSubscription();
    ents[p] = makeEntitlement(p);
  });

  return {
    request_date:    new Date().toISOString(),
    request_date_ms: Date.now(),
    subscriber: {
      original_app_user_id:                  userId || "anonymous",
      original_application_version:          "1.0",
      original_purchase_date:                START,
      first_seen:                            START,
      last_seen:                             new Date().toISOString(),
      management_url:                        null,
      subscriptions:                         subs,
      entitlements:                          ents,
      non_subscriptions:                     {},
      other_purchases:                       {},
      active_subscriptions:                  PRODUCTS,
      all_purchased_product_identifiers:     PRODUCTS,
      all_expiration_dates_by_product:       Object.fromEntries(PRODUCTS.map(p => [p, EXPIRE])),
      all_purchased_dates_by_product:        Object.fromEntries(PRODUCTS.map(p => [p, START])),
    }
  };
}

function buildOfferingsBody() {
  return {
    current_offering_id: "gold",
    offerings: [
      {
        identifier:  "gold",
        description: "Locket Gold",
        metadata:    {},
        packages: PRODUCTS.map(pid => ({
          identifier:                  "$rc_annual",
          platform_product_identifier: pid,
          product: {
            identifier:    pid,
            title:         "Locket Gold",
            description:   "Locket Gold Annual",
            price:         0.00,
            price_string:  "$0.00",
            currency_code: "USD",
            intro_price:   null,
          }
        }))
      }
    ]
  };
}

const CORS_HEADERS = {
  "Access-Control-Allow-Origin":  "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "*",
  "Content-Type":                 "application/json",
  "Cache-Control":                "public, max-age=315360000, immutable",
  "Expires":                      "Fri, 31 Dec 2099 23:59:59 GMT",
};

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const url      = new URL(request.url);
    const pathname = url.pathname;

    // /v1/subscribers/:userId  or  /v2/subscribers/:userId
    const subMatch = pathname.match(/\/v[12]\/subscribers\/([^/?]+)/);
    if (subMatch) {
      const body = buildSubscriberBody(decodeURIComponent(subMatch[1]));
      return new Response(JSON.stringify(body), { status: 200, headers: CORS_HEADERS });
    }

    // /v1/receipts
    if (pathname.endsWith("/receipts")) {
      // Parse userId from request body if possible
      let userId = "anonymous";
      try {
        const rb = await request.json();
        userId = rb.app_user_id || userId;
      } catch (_) {}
      const body = buildSubscriberBody(userId);
      return new Response(JSON.stringify(body), { status: 200, headers: CORS_HEADERS });
    }

    // /v1/offerings
    if (pathname.endsWith("/offerings")) {
      return new Response(JSON.stringify(buildOfferingsBody()), { status: 200, headers: CORS_HEADERS });
    }

    // Catch-all: return Gold subscriber for anything else RC-related
    return new Response(JSON.stringify(buildSubscriberBody("anonymous")), {
      status: 200,
      headers: CORS_HEADERS,
    });
  }
};
