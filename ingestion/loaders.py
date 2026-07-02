"""Loaders par table : full refresh idempotent depuis le snapshot du seed.

Le seed régénère à chaque run un snapshot complet de la donnée synthétique ;
la couche raw doit donc refléter EXACTEMENT ce snapshot. Chaque loader :
  1. charge le CSV dans une table TEMP (COPY, rapide) ;
  2. supprime de la cible les lignes absentes du snapshot ;
  3. insère / met à jour les lignes du snapshot (upsert sur la clé naturelle).

Résultat : raw.<table> est toujours égal au CSV courant, et rejouer le
pipeline est déterministe sans laisser de ligne orpheline. C'est ce qui
garantit les tests d'unicité et de non-chevauchement de dbt. Un simple
INSERT ON CONFLICT DO NOTHING accumulait au contraire les lignes obsolètes
quand la génération changeait (même compte, nouveaux ids), créant des
abonnements qui se chevauchaient dans le temps.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed

from ingestion.db import pg_conn

# mapping CSV vers (table_pg, colonne_pk, colonnes dans l'ordre du CSV)
_TABLES = {
    "accounts": (
        "raw.accounts", "account_id",
        ["account_id", "company_name", "industry", "country", "plan", "seats",
         "signup_ts", "churned_ts", "acquisition_ch"],
    ),
    "subscriptions": (
        "raw.subscriptions", "subscription_id",
        ["subscription_id", "account_id", "plan", "seats", "mrr",
         "valid_from", "valid_to"],
    ),
    "invoices": (
        "raw.invoices", "invoice_id",
        ["invoice_id", "account_id", "amount", "issued_ts", "paid_ts", "status"],
    ),
    "events": (
        "raw.events", "event_id",
        ["event_id", "account_id", "user_id", "event_type", "event_ts", "properties"],
    ),
    "tickets": (
        "raw.tickets", "ticket_id",
        ["ticket_id", "account_id", "category", "opened_ts", "closed_ts",
         "priority", "csat"],
    ),
}


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
def load_csv(csv_path: Path, key: str) -> int:
    """Charge un CSV dans ``raw.<table>``. Renvoie le nombre de lignes insérées."""
    if key not in _TABLES:
        raise ValueError(f"Clé de table inconnue : {key}")

    pg_table, pk, cols = _TABLES[key]
    df = pd.read_csv(csv_path, parse_dates=[c for c in cols if c.endswith("_ts")
                                            or c in {"valid_from", "valid_to"}])
    # on garde seulement les colonnes attendues (les extras ex: index parasite sont supprimées)
    df = df[[c for c in cols if c in df.columns]]

    # pandas lit les colonnes int-avec-None en float64 (ex: csat, seats)
    # on repasse en nullable Int64 pour que COPY envoie "4" et non "4.0"
    _NULLABLE_INT_COLS = {"csat", "seats"}
    for col in _NULLABLE_INT_COLS:
        if col in df.columns:
            df[col] = df[col].astype(pd.Int64Dtype())

    if df.empty:
        logger.warning("  {} : CSV vide, ignoré", key)
        return 0

    col_list    = ", ".join(cols)
    update_cols = [c for c in cols if c != pk]
    set_clause  = ", ".join(f"{c} = excluded.{c}" for c in update_cols)

    with pg_conn() as conn:
        with conn.cursor() as cur:
            # staging dans une table temp au schéma identique
            cur.execute(f"CREATE TEMP TABLE _stage (LIKE {pg_table} INCLUDING ALL) ON COMMIT DROP;")
            # COPY est nettement plus rapide que executemany sur des milliers de lignes
            buf = _df_to_csv_buffer(df, cols)
            cur.copy_expert(
                f"COPY _stage ({col_list}) FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')",
                buf,
            )
            # Full refresh atomique : la cible doit refléter exactement le snapshot.
            # 1. retrait des lignes qui ne sont plus dans le snapshot (anti-accumulation)
            cur.execute(
                f"DELETE FROM {pg_table} t "
                f"WHERE NOT EXISTS (SELECT 1 FROM _stage s WHERE s.{pk} = t.{pk});"
            )
            # 2. upsert des lignes du snapshot (created_at préservé sur les lignes existantes)
            cur.execute(
                f"INSERT INTO {pg_table} ({col_list}) "
                f"SELECT {col_list} FROM _stage "
                f"ON CONFLICT ({pk}) DO UPDATE SET {set_clause};"
            )
            synced = cur.rowcount
        conn.commit()

    logger.info("  {} : {:>7,} lignes synchronisées (full refresh)", key, synced)
    return synced


def _df_to_csv_buffer(df: pd.DataFrame, cols: list[str]):
    from io import StringIO
    buf = StringIO()
    df.to_csv(buf, index=False, columns=cols, na_rep="")
    buf.seek(0)
    return buf
