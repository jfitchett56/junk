# Positioning — POS History Migration (working draft)

*Grounded in `pos-migration-demand-research.md`. One page for a landing page / investor blurb / sales sheet.*

---

## The one-liner

**"We move your sales history, not just your menu."**
Vendor-neutral POS migration that brings your full transaction ledger — receipts, year-over-year reporting, customer & loyalty data — onto whatever modern system you choose. 150+ systems supported, any source to any destination.

## The problem (in the buyer's words)

> *"I'd switch, but I have 6½ years of sales data in there and I'm scared I'll lose it — and I still need it for taxes."*

- Modern cloud POSes onboard a **catalog** well and a **transaction ledger** poorly. Intuit's own recommended QuickBooks-POS→Shopify path **drops order history, POs, discounts, and customer order history**. Lightspeed admits sales history **can't transfer** to Shopify. Cross-vendor imports cap at 60 days / 90 days / 1,000 rows.
- So merchants do the worst thing: they **keep the dead box running** just to read old sales — or they don't switch at all.
- Legal retention (IRS 3–6 yrs, HMRC 6 yrs, ATO 5–7 yrs) means "just start fresh" isn't an option.

## Why now

QuickBooks Desktop POS was discontinued (end-of-sale Oct 2023; payments/connected services dead). A large install base is being **forced** off — with the single most-recommended destination explicitly unable to carry their history.

## Why us (vs. everyone else)

| Today's options | The gap | Our edge |
|---|---|---|
| Resellers/ISOs (Genius POS, SkyTab, Toast onboarding) | **Destination-locked** — only move you onto *their* platform; config-deep, history-light | **Vendor-neutral, any→any** — we serve the merchant's choice |
| QB-POS bookkeeping shops (TSZ, POS Pros, Fourlane…) | Even they concede "limited support for **historical sales data**" | We actually **land the ledger**, not just items/customers |
| Retail e-comm tools (Next-Cart, LiteExtension) | Catalog/customers only; transaction history "not practical" | History is our **headline**, not our footnote |

Three structural moats: **(1)** no destination lock-in, **(2)** 150 sources spans a category fragmented across three separate worlds, **(3)** transaction history is everyone's admitted weak spot.

## Beachhead → expansion

1. **Beachhead:** *"QuickBooks Desktop POS → any modern POS, with your full sales history."* Forced move, urgent, legal driver, and the incumbents can't do the history piece.
2. **Expand (restaurant):** Aloha / MICROS → Toast / Square / SkyTab — with year-over-year reporting intact.
3. **Expand (retail):** Clover ↔ Square, Lightspeed/Vend → Shopify POS — fill the CSV-wall gap vendors admit in their own docs.

## Productized deliverables

- **Full history migration** into the destination where it'll fit.
- **Compliance-grade audit archive** (machine-sensible, queryable, audit-ready) for the history the destination *can't* hold — this is what finally lets the merchant decommission the old box. *Sellable on its own.*
- **White-label for resellers/ISOs** who already do menu setup and decline the data piece — turns competitors into a distribution channel.

## Proof points to collect next (validation)

- Live count of QB-POS-exit threads (Reddit API + vendor communities) — see `reddit_demand_census.py`.
- 3–5 reference migrations with before/after data-completeness numbers.
- Per-pair confirmation of current destination import limits (they change).
