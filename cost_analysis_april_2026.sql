-- =============================================================================
-- Cost-analysis report: master-account product costs vs. lower regional prices
-- Period: April 2026 (configurable below)
-- Dialect: PostgreSQL (psql)
-- =============================================================================
--
-- WHAT THIS REPORT DOES
--   For one master account, over April 2026, it reports the average unit cost of
--   each product the account bought, then finds the lowest price the SAME product
--   was bought for anywhere in the master account's region(s) -- including:
--     * the master account's own other branches (different branch IDs), and
--     * branches belonging to OTHER master accounts in the same region(s).
--   Rows are limited to genuine opportunities (someone paid less) and ranked by
--   the money you could have saved at that lower price.
--
-- IMPORTANT - SCHEMA ASSUMPTIONS
--   This was written WITHOUT access to your live database, so the table and
--   column names below are assumptions for a typical invoice system. Run the
--   discovery queries in SECTION 0 first, then adjust the names in SECTION 1's
--   `schema_map` comment block / the FROM-JOIN clauses to match reality.
--
--   Assumed tables / columns:
--     branches(branch_id, master_account_id, region_id)
--     invoices(invoice_id, branch_id, invoice_date)
--     invoice_lines(invoice_id, product_id, quantity, unit_price)
--     products(product_id, name, sku)         -- sku optional
--
--   Notes:
--     * "Average cost" is computed quantity-weighted: SUM(qty*price)/SUM(qty).
--       Simple average and min/max are included for transparency.
--     * Line spend uses quantity * unit_price. If your invoice_lines table has a
--       discounted line-amount column (e.g. net_amount, line_total), swap that in
--       for `quantity * unit_price` for more accurate spend/avg.
--     * invoice_date is assumed to be a DATE/TIMESTAMP. If your date lives on the
--       line rather than the invoice, move the date filter into invoice_lines.
-- =============================================================================


-- =============================================================================
-- SECTION 0 -- DISCOVERY (run these first to confirm the real schema)
-- =============================================================================

-- 0a. List all user tables.
-- SELECT table_schema, table_name
-- FROM information_schema.tables
-- WHERE table_schema NOT IN ('pg_catalog','information_schema')
-- ORDER BY 1,2;

-- 0b. Columns for the tables that look invoice/branch/product/region related.
-- SELECT table_name, column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name ILIKE ANY (ARRAY
--       ['%invoice%','%branch%','%product%','%account%','%region%','%item%','%line%'])
-- ORDER BY table_name, ordinal_position;

-- 0c. Sanity check: how many April-2026 invoice lines exist, and the date range.
-- SELECT MIN(invoice_date), MAX(invoice_date), COUNT(*)
-- FROM invoices
-- WHERE invoice_date >= DATE '2026-04-01' AND invoice_date < DATE '2026-05-01';


-- =============================================================================
-- SECTION 1 -- THE REPORT (exact product match)
-- =============================================================================
-- EDIT the three values in `params`, then run.
-- If your names differ from the assumptions, fix them in the JOINs below.

WITH params AS (
    SELECT
        12345::bigint     AS master_account_id,  -- <<< EDIT: your master account id
        DATE '2026-04-01' AS period_start,       -- inclusive
        DATE '2026-05-01' AS period_end          -- exclusive (first day of next month)
),

-- Branches that belong to the target master account.
master_branches AS (
    SELECT b.branch_id, b.region_id
    FROM branches b
    JOIN params p ON b.master_account_id = p.master_account_id
),

-- The region(s) those branches sit in.
target_regions AS (
    SELECT DISTINCT region_id FROM master_branches
),

-- Every branch in those region(s), regardless of master account
-- (this is the universe we benchmark prices against).
peer_branches AS (
    SELECT b.branch_id, b.master_account_id, b.region_id
    FROM branches b
    WHERE b.region_id IN (SELECT region_id FROM target_regions)
),

-- April-2026 line items bought by the MASTER account's branches.
master_lines AS (
    SELECT il.product_id, il.quantity, il.unit_price
    FROM invoice_lines il
    JOIN invoices i        ON i.invoice_id = il.invoice_id
    JOIN master_branches mb ON mb.branch_id = i.branch_id
    CROSS JOIN params p
    WHERE i.invoice_date >= p.period_start
      AND i.invoice_date <  p.period_end
),

-- The master account's cost per product.
master_product AS (
    SELECT
        product_id,
        SUM(quantity)                                       AS master_qty,
        SUM(quantity * unit_price)                          AS master_spend,
        SUM(quantity * unit_price) / NULLIF(SUM(quantity),0) AS avg_unit_cost,  -- qty-weighted
        AVG(unit_price)                                     AS simple_avg_price,
        MIN(unit_price)                                     AS min_paid,
        MAX(unit_price)                                     AS max_paid,
        COUNT(*)                                            AS line_count
    FROM master_lines
    GROUP BY product_id
),

-- April-2026 line items bought by ANY branch in the region(s).
peer_lines AS (
    SELECT
        il.product_id,
        pb.branch_id,
        pb.master_account_id,
        il.unit_price
    FROM invoice_lines il
    JOIN invoices i       ON i.invoice_id = il.invoice_id
    JOIN peer_branches pb ON pb.branch_id = i.branch_id
    CROSS JOIN params p
    WHERE i.invoice_date >= p.period_start
      AND i.invoice_date <  p.period_end
),

-- Lowest regional price per product, and who got it.
peer_best AS (
    SELECT DISTINCT ON (product_id)
        product_id,
        unit_price        AS best_regional_price,
        branch_id         AS best_branch_id,
        master_account_id AS best_master_account_id
    FROM peer_lines
    ORDER BY product_id, unit_price ASC
)

SELECT
    pr.name                                          AS product,
    pr.sku                                           AS sku,
    mp.master_qty                                    AS qty_bought_apr,
    ROUND(mp.avg_unit_cost, 4)                       AS your_avg_unit_cost,
    ROUND(mp.simple_avg_price, 4)                    AS your_simple_avg,
    ROUND(mp.min_paid, 4)                            AS your_min_paid,
    ROUND(mp.max_paid, 4)                            AS your_max_paid,
    ROUND(pb.best_regional_price, 4)                 AS best_regional_price,
    pb.best_branch_id,
    pb.best_master_account_id,
    (pb.best_master_account_id = p.master_account_id) AS best_is_within_your_org,
    ROUND(mp.avg_unit_cost - pb.best_regional_price, 4)               AS unit_saving,
    ROUND((mp.avg_unit_cost - pb.best_regional_price) * mp.master_qty, 2) AS potential_saving_apr,
    ROUND(100.0 * (mp.avg_unit_cost - pb.best_regional_price)
          / NULLIF(mp.avg_unit_cost, 0), 1)          AS pct_cheaper
FROM master_product mp
JOIN peer_best pb ON pb.product_id = mp.product_id
JOIN products  pr ON pr.product_id = mp.product_id
CROSS JOIN params p
WHERE pb.best_regional_price < mp.avg_unit_cost     -- opportunities only
ORDER BY potential_saving_apr DESC;


-- =============================================================================
-- SECTION 2 -- VARIANTS / TUNING
-- =============================================================================
--
-- A) Show ALL products (not just opportunities): delete the WHERE line
--    `pb.best_regional_price < mp.avg_unit_cost`.
--
-- B) Wider comparison window for more price samples: the peer_lines benchmark
--    above only looks at April. To compare April purchases against the best
--    price seen over, say, the whole quarter, give peer_lines its own dates:
--      ... WHERE i.invoice_date >= DATE '2026-01-01'
--              AND i.invoice_date <  DATE '2026-05-01'
--    (leave master_lines on April only).
--
-- C) "Similar" products, not just identical product_id. If products carry a
--    category/group key, benchmark within the category instead of by product_id:
--      - add pr.category_id to master_product / peer_lines (join products),
--      - in peer_best use DISTINCT ON (category_id) ordered by unit_price,
--      - join master_product to peer_best on category_id.
--    True text-similarity (fuzzy SKU/description matching) needs pg_trgm; ask and
--    I'll write that version once the product table layout is known.
--
-- D) Exclude your own branches from the benchmark (compare only against OTHER
--    masters): add to peer_branches' WHERE:
--      AND b.master_account_id <> (SELECT master_account_id FROM params)
-- =============================================================================
