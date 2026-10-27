"""Certified sales methods.

Each public function here is a *certified tool*: a vetted, documented way to
answer a common business question. Prefer these over hand-written SQL against
the sales database, because they encode rules that aren't visible in the
schema (currency conversion, excluding training sessions).
"""

from __future__ import annotations

from datetime import date
from importlib import resources
from typing import Iterable, Literal, Optional, Union

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

Grain = Literal["day", "week", "month", "quarter", "year"]
_GRAINS = {"day", "week", "month", "quarter", "year"}
GroupBy = Literal["category", "branch", "product"]
_GROUP_BYS = {"category", "branch", "product"}

_SQL_FILE = "global_branches_sanitized_sales.sql"


def get_sql() -> str:
    """Return the exact SQL that ``global_branches_sanitized_sales`` runs."""
    return resources.files("coda_certified").joinpath("sql", _SQL_FILE).read_text()


def _normalize_url(url: str) -> str:
    # Accept plain postgresql:// URLs (as people usually store them in env
    # vars) and route them through the psycopg 3 driver.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def global_branches_sanitized_sales(
    db: Union[str, Engine, Connection],
    start_date: Union[str, date],
    end_date: Union[str, date],
    grain: Grain = "quarter",
    group_by: Optional[GroupBy] = None,
    branch_codes: Optional[Iterable[str]] = None,
    categories: Optional[Iterable[str]] = None,
    include_training: bool = False,
) -> pd.DataFrame:
    """Certified sales totals across all branches, in USD.

    Parameters
    ----------
    db:
        A database URL (e.g. ``os.environ["SALES_DB_URL"]``), a SQLAlchemy
        ``Engine``, or an open ``Connection``.
    start_date:
        Inclusive start of the range. Maps to ``sold_at >= :start_date``.
    end_date:
        Exclusive end of the range. Maps to ``sold_at < :end_date``.
        For all of Q1–Q3 2026 use ``start_date="2026-01-01"``,
        ``end_date="2026-10-01"``.
    grain:
        Bucket size for ``period``: ``"day"``, ``"week"``, ``"month"``,
        ``"quarter"`` (default) or ``"year"``.
        Maps to ``date_trunc(:grain, sold_at)``.
    group_by:
        ``"category"``, ``"branch"`` or ``"product"`` adds a column with that
        name and one row per period and group. ``None`` (default) returns
        totals per period. Maps to the ``group_key`` expression.
    branch_codes:
        Optional list of branch codes (e.g. ``["AUS", "MTY"]``). ``None``
        (default) includes every branch. Maps to ``b.code = ANY(:branch_codes)``.
    categories:
        Optional list of category names (e.g. ``["Electronics"]``). ``None``
        (default) includes every category. Maps to ``c.name = ANY(:categories)``.
    include_training:
        ``False`` (default) drops sales from POS sessions in ``training`` mode,
        which are not real revenue. Maps to ``ps.mode = 'live'``.

    Returns
    -------
    pandas.DataFrame with columns:
        ``period`` (date, start of each bucket),
        ``<group_by>`` (str, only when ``group_by`` is set),
        ``sales_usd`` (float, total converted to USD),
        ``transactions`` (int).

    Notes
    -----
    Amounts are converted from the currency each branch's POS recorded them
    in (``branch_currency_periods``) using monthly rates in ``fx_rates``.
    A plain ``SUM(sales.amount)`` mixes currencies and includes training
    sales, so it is not comparable across branches.
    """
    if grain not in _GRAINS:
        raise ValueError(f"grain must be one of {sorted(_GRAINS)}, got {grain!r}")
    if group_by is not None and group_by not in _GROUP_BYS:
        raise ValueError(f"group_by must be one of {sorted(_GROUP_BYS)} or None, got {group_by!r}")

    params = {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "grain": grain,
        "group_by": group_by,
        "branch_codes": list(branch_codes) if branch_codes is not None else None,
        "categories": list(categories) if categories is not None else None,
        "include_training": include_training,
    }
    query = text(get_sql())

    if isinstance(db, str):
        engine = create_engine(_normalize_url(db))
        try:
            with engine.connect() as conn:
                return _run(conn, query, params, group_by)
        finally:
            engine.dispose()
    if isinstance(db, Engine):
        with db.connect() as conn:
            return _run(conn, query, params, group_by)
    return _run(db, query, params, group_by)


def _run(conn: Connection, query, params, group_by) -> pd.DataFrame:
    rows = conn.execute(query, params).mappings().all()
    df = pd.DataFrame(rows, columns=["period", "group_key", "sales_usd", "transactions"])
    if not df.empty:
        df["period"] = pd.to_datetime(df["period"]).dt.date
        df["sales_usd"] = df["sales_usd"].astype(float)
        df["transactions"] = df["transactions"].astype(int)
    if group_by is None:
        return df.drop(columns="group_key")
    return df.rename(columns={"group_key": group_by})


# Catalog name, as listed in CODA's Certified Tools app.
GlobalBranchesSanitizedSales = global_branches_sanitized_sales
