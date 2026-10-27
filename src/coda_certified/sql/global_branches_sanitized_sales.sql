-- GlobalBranchesSanitizedSales
-- Certified sales totals across all branches, in USD, excluding non-revenue
-- POS activity. Optionally broken down by category, branch or product.
--
-- Parameters
--   :start_date        inclusive lower bound on sold_at (date)
--   :end_date          exclusive upper bound on sold_at (date)
--   :grain             'day' | 'week' | 'month' | 'quarter' | 'year'
--   :group_by          'category' | 'branch' | 'product', or NULL for totals only
--   :branch_codes      text[] of branch codes to keep, or NULL for all branches
--   :categories        text[] of category names to keep, or NULL for all
--   :include_training  when false (default), drops POS training sessions
--
-- What it sanitizes
--   1. Currency: each sale is converted from the currency its branch's POS
--      recorded it in (branch_currency_periods) to USD, using the monthly rate
--      in fx_rates.
--   2. Training: sales from POS sessions in 'training' mode are excluded.

WITH scoped_sales AS (
    SELECT sa.sale_id,
           sa.branch_id,
           sa.sold_at,
           sa.amount,
           b.code  AS branch_code,
           c.name  AS category,
           p.name  AS product
    FROM sales sa
    JOIN pos_sessions ps ON ps.session_id  = sa.session_id
    JOIN branches     b  ON b.branch_id    = sa.branch_id
    JOIN products     p  ON p.product_id   = sa.product_id
    JOIN categories   c  ON c.category_id  = p.category_id
    WHERE sa.sold_at >= CAST(:start_date AS date)
      AND sa.sold_at <  CAST(:end_date   AS date)
      AND (CAST(:include_training AS boolean) OR ps.mode = 'live')
      AND (CAST(:branch_codes AS text[]) IS NULL
           OR b.code = ANY (CAST(:branch_codes AS text[])))
      AND (CAST(:categories AS text[]) IS NULL
           OR c.name = ANY (CAST(:categories AS text[])))
)
SELECT date_trunc(CAST(:grain AS text), s.sold_at)::date AS period,
       CASE CAST(:group_by AS text)
           WHEN 'category' THEN s.category
           WHEN 'branch'   THEN s.branch_code
           WHEN 'product'  THEN s.product
           ELSE 'All'
       END                                              AS group_key,
       round(sum(s.amount * fx.usd_rate), 2)            AS sales_usd,
       count(*)                                         AS transactions
FROM scoped_sales s
JOIN branch_currency_periods cp
  ON cp.branch_id = s.branch_id
 AND s.sold_at::date >= cp.valid_from
 AND (cp.valid_to IS NULL OR s.sold_at::date <= cp.valid_to)
JOIN fx_rates fx
  ON fx.currency = cp.currency
 AND fx.month    = date_trunc('month', s.sold_at)::date
GROUP BY 1, 2
ORDER BY 1, 2;
