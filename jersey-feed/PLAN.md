# NHL Jersey Feed — Plan

## Context
Build a mobile app with an Instagram-style vertical feed where each NHL Fanatics Premium (Premium/Breakaway-tier) jersey listing from resale sites appears as a post, using the listing's own photos. One place to scroll and find jerseys for sale. Direct scraping of retailers (Fanatics) is dropped; focus is resale marketplaces, using official APIs where they exist.

## Sources (what is actually allowed)
| Site | Access | Status |
|---|---|---|
| eBay | Official Browse API (free developer account, OAuth app token). Supports keyword/category search, item images, price, condition, size, seller, and affiliate links | **Phase 1** |
| Etsy | Official Open API v3 | Possible later, low NHL jersey volume |
| Poshmark | No public API; terms of service prohibit scraping | **Not included** unless a licensed/partner feed exists |
| Mercari, Grailed, Depop | No open public API / ToS restrict scraping | **Not included** |
| Others | Check each site's API/ToS before adding | Add per-source adapters only if an official API or feed exists |

Result: launch with eBay, which has by far the largest NHL jersey inventory, then add sources one at a time behind a common adapter interface. Optional: join eBay Partner Network so outbound listing links earn affiliate commission.

## Architecture
- **App**: Expo / React Native (TypeScript), tested on phone via Expo Go.
- **Backend**: small Node/TypeScript service on Railway with Postgres. A scheduled job (every ~2-3h) calls source adapters, normalizes listings, de-duplicates, and marks ended listings inactive. A simple REST API (`GET /listings?team=&size=&maxPrice=&cursor=`) serves the feed.
- **Adapter interface**: each source implements `fetchListings(): Listing[]` returning a normalized shape (id, source, title, team, size, price, currency, condition, images[], url, endsAt, seller).
- **Filtering**: "Fanatics Premium" is matched via title/item-specifics keywords (e.g. "Fanatics", "Premium", "Authentic Pro", "Breakaway") plus NHL team name parsing; exclude lots, kids, and non-jersey items.

## App screens
1. **Feed**: infinite-scroll posts. Each post: header (team logo/name + source badge, like a profile row), swipeable image carousel, price/size/condition line, caption (title), "View listing" button opening the original page. Pull to refresh.
2. **Filters**: team, size, price range, condition.
3. **Saved**: heart a listing (double-tap to like), stored on-device.
4. Instagram look: white/black themes, system font, rounded avatar for team, bottom tab bar.

## Phases
1. Backend + eBay adapter + DB + API (verify real listings come back).
2. Expo app with feed and carousel using live API.
3. Filters + saved.
4. Scheduled refresh, ended-listing cleanup, error monitoring.
5. Optional: price-drop push notifications, more sources, App Store release.

## Prerequisites from the user
- eBay developer account (developer.ebay.com) for API keys.
- Railway account with payment method (about $5-10/mo).

## Verification
- Run adapter against live eBay API; confirm normalized listings with images and working links.
- Hit `/listings` with filters and check results.
- Run the app in Expo Go on a phone: scroll feed, swipe images, open a listing, filter, save.
- Confirm the scheduled job runs and removes ended listings.
