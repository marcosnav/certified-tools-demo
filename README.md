# coda-certified-tools

Pre-vetted Python methods and SQL queries for common business questions. Each
tool here is listed in CODA's **Certified Tools** app.

## Install

```bash
pip install "coda-certified-tools @ git+https://github.com/marcosnav/certified-tools-demo.git@v1.1.0"
```

## GlobalBranchesSanitizedSales

Sales totals across all branches, in USD, with POS training sessions excluded.
Optionally broken down by category, branch or product.

```python
import os
from coda_certified import global_branches_sanitized_sales

df = global_branches_sanitized_sales(
    os.environ["SALES_DB_URL"],
    start_date="2026-01-01",
    end_date="2026-10-01",   # exclusive
    grain="month",
    group_by="category",
)
# columns: period (date), category (str), sales_usd (float), transactions (int)
```

| Parameter | Default | Effect on the SQL |
| --- | --- | --- |
| `start_date` | required | `sold_at >= :start_date` |
| `end_date` | required | `sold_at < :end_date` (exclusive) |
| `grain` | `"quarter"` | `date_trunc(:grain, sold_at)`; one of day, week, month, quarter, year |
| `group_by` | `None` | `"category"`, `"branch"` or `"product"` adds that column; `None` returns totals |
| `branch_codes` | `None` (all) | `b.code = ANY(:branch_codes)` |
| `categories` | `None` (all) | `c.name = ANY(:categories)` |
| `include_training` | `False` | `False` keeps only `ps.mode = 'live'` sessions |

### Why not `SUM(sales.amount)`?

`sales.amount` is recorded in whatever currency the branch's POS used at the
time (see `branch_currency_periods`), and the table also contains sales from
staff training sessions. This tool converts every sale to USD with the monthly
rate in `fx_rates` and drops training sessions.

The exact SQL is in [`src/coda_certified/sql/global_branches_sanitized_sales.sql`](src/coda_certified/sql/global_branches_sanitized_sales.sql),
and `coda_certified.get_sql()` returns it at runtime. Machine-readable metadata
for CODA's catalog is in [`src/coda_certified/catalog.json`](src/coda_certified/catalog.json).
