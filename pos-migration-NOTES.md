# POS Migration — Project Notes

**Project:** Validate demand for POS data-migration (setup **+** historical sales data) and define the market opportunity for a 150+ POS interface library.
**Branch:** `claude/pos-migration-demand-vfgk34`
**Status:** Research + positioning + landing page complete. Demand-volume census scripted but not yet run (needs Reddit API creds).
**Last updated:** 2026-06-25

---

## Hypothesis & verdict

> *Many POS users are stuck on legacy systems because conversion help is scarce — especially fear of losing historical sales data — and most migration services only handle menu/catalog setup, not data.*

**Verdict: Largely CONFIRMED.** The data-migration gap is documented in vendors' *own* support docs (QB POS→Shopify drops order history; Lightspeed→Shopify can't transfer sales history; 60-day / 90-day / 1,000-row caps). Legal retention (IRS 3–6 yrs, HMRC 6 yrs, ATO 5–7 yrs) makes "start fresh" a non-option. One correction to the first draft: the space is **not empty** — a fragmented, mostly destination-locked service market exists, but history migration is the admitted weak spot even among specialists.

## Deliverables (all on this branch)

| File | Purpose |
|---|---|
| `pos-migration-demand-research.md` | Full cited research report — evidence, competitive landscape, ranked from→to pairs, measurement caveat |
| `positioning-pos-history-migration.md` | One-page pitch: "We move your sales history, not just your menu" |
| `landing/index.html` | Self-contained responsive landing page (placeholder brand "LedgerShift") |
| `reddit_demand_census.py` | Official Reddit-API census to get hard thread/engagement volume per migration theme |

## The opportunity (sharpened thesis)

Three structural openings a vendor-neutral, history-first, any→any service exploits:
1. **No destination lock-in** — competitors only move you onto *their* platform.
2. **Source breadth** — 150 sources spans a category fragmented across QB-POS bookkeepers, restaurant resellers, and retail e-comm tools.
3. **History is everyone's weak spot** — stated outright by competitors.

**Beachhead:** QuickBooks Desktop POS → any modern POS, *with full sales history* (forced move post-discontinuation, legal driver, incumbents can't do the ledger).
**Differentiated deliverable:** compliance-grade audit archive for history the destination can't hold — lets the merchant retire the old box; sellable on its own.

## Highest-demand from → to pairs

1. **QuickBooks Desktop POS → Shopify / Lightspeed / Clover** (Tier 1 — best)
2. **Aloha → Toast**, **MICROS → Toast / SkyTab / Square** (Tier 2)
3. **Clover ↔ Square**, **Lightspeed/Vend → Shopify POS** (Tier 3)

## Open items / next steps

- [ ] **Run `reddit_demand_census.py`** with Reddit API creds to get hard volume numbers behind the rankings.
- [ ] **Rebrand the landing page** — replace placeholder name "LedgerShift" + `hello@ledgershift.example` contact.
- [ ] **Wire CTA to a real lead form** (Formspree/Netlify) instead of mailto.
- [ ] Optional: add a "systems we migrate from" logo grid / searchable 150+ list to the page.
- [ ] Optional: stand up a public link (GitHub Pages / static host).
- [ ] **Re-verify per-vendor import limits** before publishing any claims (they change).
- [ ] Gather 3–5 reference migrations with before/after data-completeness numbers.

## Notes / caveats

- Exact forum thread counts were **not retrievable** during research (Reddit hard-blocked, no `site:` search, many forums 403 to automated fetch). Demand evidence rests on breadth-of-discussion + primary docs + the existence of a QB-POS migration consultancy cottage industry. The census script closes this gap once run.
- No PR has been opened (none requested). Work lives on the feature branch only.
