-- =============================================================================
-- New-branch report: branch IDs ("2020id"s) that FIRST showed up in the last
-- two weeks.
-- Dialect: Microsoft SQL Server (T-SQL)  -- run in SSMS / azure-data-studio / sqlcmd
-- Server:  zero-paper.com,1433  (see run_report.py for the pyodbc runner)
-- =============================================================================
--
-- WHAT THIS REPORT DOES
--   "First showed" is defined by ACTIVITY, not by a registration field: a branch
--   is new if its EARLIEST invoice anywhere in the database falls inside the
--   window. That definition needs no created_at/registered_on column (which may
--   not exist, or may be backfilled), and it answers the practical question --
--   which branches started transacting with us in the last 14 days.
--   If your branches table does carry a real creation date, SECTION 2 variant B
--   gives you that version instead.
--
--   The first output column, new_branches_in_window, repeats the total count on
--   every row, so a single run answers both "how many" and "which ones".
--   Zero rows returned = zero new branches in the window.
--
-- IMPORTANT - SCHEMA ASSUMPTIONS
--   Same assumptions as cost_analysis_april_2026.sql, written WITHOUT access to
--   the live database. Run SECTION 0 first and fix the names below to match.
--     branches(branch_id, master_account_id, region_id, name)
--     invoices(invoice_id, branch_id, invoice_date)
--
--   On the name "2020id": if the branch key is literally a column named 2020id,
--   T-SQL will NOT accept it unquoted -- an identifier cannot start with a digit.
--   Write it bracketed everywhere: b.[2020id], i.[2020id]. Query 0b below finds
--   the real column name for you.
-- =============================================================================


-- =============================================================================
-- SECTION 0 -- DISCOVERY (run these first to confirm the real schema)
-- =============================================================================

-- 0a. List all base tables.
-- SELECT TABLE_SCHEMA, TABLE_NAME
-- FROM INFORMATION_SCHEMA.TABLES
-- WHERE TABLE_TYPE = 'BASE TABLE'
-- ORDER BY TABLE_SCHEMA, TABLE_NAME;

-- 0b. Find the "2020id" column -- whatever it is actually called.
-- SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
-- FROM INFORMATION_SCHEMA.COLUMNS
-- WHERE COLUMN_NAME LIKE '%2020%'
--    OR COLUMN_NAME LIKE '%branch%'
--    OR COLUMN_NAME LIKE '%store%'
--    OR COLUMN_NAME LIKE '%site%'
-- ORDER BY TABLE_NAME, ORDINAL_POSITION;

-- 0c. Look for a genuine creation/registration date on branches
--     (enables SECTION 2 variant B).
-- SELECT COLUMN_NAME, DATA_TYPE
-- FROM INFORMATION_SCHEMA.COLUMNS
-- WHERE TABLE_NAME = 'branches'
--   AND (COLUMN_NAME LIKE '%creat%' OR COLUMN_NAME LIKE '%regist%'
--     OR COLUMN_NAME LIKE '%onboard%' OR COLUMN_NAME LIKE '%start%'
--     OR COLUMN_NAME LIKE '%added%'   OR COLUMN_NAME LIKE '%since%');

-- 0d. SANITY CHECK -- READ THIS BEFORE TRUSTING A ZERO RESULT.
--     If the newest invoice in the database is itself older than two weeks
--     (stale load, lagging ETL, reporting replica), the main query returns zero
--     rows for a boring reason and NOT because no branches were picked up.
-- SELECT MAX(invoice_date) AS newest_invoice,
--        COUNT(*)          AS invoices_last_14d
-- FROM invoices
-- WHERE invoice_date >= DATEADD(day, -14, CAST(SYSUTCDATETIME() AS date));


-- =============================================================================
-- SECTION 1 -- THE REPORT
-- =============================================================================

WITH params AS (
    SELECT
        CAST(14 AS int)    AS lookback_days,  -- <<< window length; 14 = two weeks
        CAST(NULL AS date) AS as_of           -- <<< NULL = today (UTC); or pin a date
),

-- Half-open window: [window_start, window_end). as_of's own day is included.
win AS (
    SELECT
        DATEADD(day, -p.lookback_days, COALESCE(p.as_of, CAST(SYSUTCDATETIME() AS date))) AS window_start,
        DATEADD(day, 1,                COALESCE(p.as_of, CAST(SYSUTCDATETIME() AS date))) AS window_end
    FROM params p
),

-- Earliest and latest invoice per branch, across ALL history.
-- No date filter here on purpose: a branch only counts as new if it has never
-- transacted before the window, so the whole history has to be scanned.
first_seen AS (
    SELECT
        i.branch_id,
        MIN(CAST(i.invoice_date AS date)) AS first_seen_date,
        MAX(CAST(i.invoice_date AS date)) AS last_seen_date,
        COUNT(DISTINCT i.invoice_id)      AS invoices_ever
    FROM invoices i
    GROUP BY i.branch_id
)

SELECT
    COUNT(*) OVER ()                                        AS new_branches_in_window,
    fs.branch_id                                            AS branch_id,      -- the "2020id"
    b.name                                                  AS branch_name,
    b.master_account_id,
    b.region_id,
    fs.first_seen_date,
    fs.last_seen_date,
    fs.invoices_ever,
    DATEDIFF(day, fs.first_seen_date,
             COALESCE(pr.as_of, CAST(SYSUTCDATETIME() AS date)))  AS days_since_first_seen,
    CASE WHEN b.branch_id IS NULL THEN 1 ELSE 0 END         AS orphan_no_branch_row
FROM first_seen fs
LEFT JOIN branches b ON b.branch_id = fs.branch_id
CROSS JOIN win w
CROSS JOIN params pr
WHERE fs.first_seen_date >= w.window_start
  AND fs.first_seen_date <  w.window_end
ORDER BY fs.first_seen_date DESC, fs.branch_id;


-- =============================================================================
-- SECTION 2 -- VARIANTS / TUNING
-- =============================================================================
--
-- A) Count only (no detail rows):
--      WITH ... (same params/win/first_seen CTEs) ...
--      SELECT COUNT(*) AS new_branches_in_window
--      FROM first_seen fs CROSS JOIN win w
--      WHERE fs.first_seen_date >= w.window_start
--        AND fs.first_seen_date <  w.window_end;
--
-- B) By a real creation date instead of first activity (if SECTION 0c found a
--    column -- substitute its real name for created_at):
--      SELECT b.branch_id, b.name, b.master_account_id, b.region_id, b.created_at
--      FROM branches b CROSS JOIN win w
--      WHERE b.created_at >= w.window_start AND b.created_at < w.window_end
--      ORDER BY b.created_at DESC;
--    Worth running BOTH: a branch created months ago that only started invoicing
--    this week shows up in SECTION 1 and not here, and vice versa. The gap
--    between the two counts is usually the interesting number.
--
-- C) New branches for ONE master account only -- add to SECTION 1's WHERE:
--      AND b.master_account_id = 12345
--    Note this is "new branch belonging to that account", not "account new to
--    us". For brand-new MASTER ACCOUNTS, group first_seen by b.master_account_id
--    instead of by branch and apply the same window test.
--
-- D) Reactivated (not new) branches -- dormant a long time, then back this week.
--    Often what people actually mean by "picked up". Replace SECTION 1's WHERE:
--      WHERE fs.last_seen_date >= w.window_start
--        AND fs.first_seen_date < DATEADD(day, -90, w.window_start)
--    and add a per-branch previous-activity gap if you want it precise.
--
-- E) Add first-window spend -- join invoice_lines for the branches that survive
--    the filter:
--      LEFT JOIN (
--          SELECT i.branch_id, SUM(il.quantity * il.unit_price) AS spend_in_window
--          FROM invoice_lines il
--          JOIN invoices i ON i.invoice_id = il.invoice_id
--          CROSS JOIN win w
--          WHERE i.invoice_date >= w.window_start AND i.invoice_date < w.window_end
--          GROUP BY i.branch_id
--      ) s ON s.branch_id = fs.branch_id
--
-- F) Performance: first_seen scans all of invoices. If that table is large and
--    this becomes a recurring report, an index on invoices(branch_id, invoice_date)
--    turns the MIN/MAX per branch into a cheap index scan.
-- =============================================================================
