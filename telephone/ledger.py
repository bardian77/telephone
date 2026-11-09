"""Run ledger: one row per generation in SQLite, plus an append-only spend log.

The ledger is the single source of truth. Figures, the web export and the API all read it.
It is local state (ignored by git). To keep results, `save_results` writes one experiment as a
sorted JSONL snapshot that can be committed and read back with `import_jsonl`; there is no live
JSONL mirror, because an append-only mirror of an upsert table drifts from it.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .models import GenerationRecord, now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS generations (
    run_id TEXT NOT NULL,
    experiment_id TEXT NOT NULL,
    chain_id TEXT NOT NULL,
    repeat INTEGER NOT NULL DEFAULT 0,
    generation INTEGER NOT NULL,
    station_sequence TEXT NOT NULL,
    output_path TEXT NOT NULL,
    output_sha TEXT NOT NULL,
    clip_dist_to_g0 REAL,
    ssim_to_g0 REAL,
    cost_usd REAL NOT NULL DEFAULT 0,
    list_price_usd REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    error TEXT,
    record JSON NOT NULL,
    PRIMARY KEY (chain_id, repeat, generation)
);
CREATE INDEX IF NOT EXISTS idx_gen_experiment ON generations(experiment_id);
CREATE INDEX IF NOT EXISTS idx_gen_run ON generations(run_id);
CREATE TABLE IF NOT EXISTS spend (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    cost_usd REAL NOT NULL DEFAULT 0,
    list_price_usd REAL NOT NULL DEFAULT 0
);
"""


class Ledger:
    def __init__(self, sqlite_path: Path, check_same_thread: bool = True):
        self.sqlite_path = Path(sqlite_path)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.sqlite_path, check_same_thread=check_same_thread)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    # -- spend log: append-only, one row per paid call --------------------------------------
    def log_spend(
        self, provider: str | None, model: str | None, cost_usd: float, list_price_usd: float
    ) -> None:
        """Record one provider call. Rows are never replaced or deleted, so the sum is the
        true lifetime spend even when generation rows are re-run or served from the cache."""
        self.conn.execute(
            "INSERT INTO spend (created_at, provider, model, cost_usd, list_price_usd) "
            "VALUES (?,?,?,?,?)",
            (now_iso(), provider, model, float(cost_usd), float(list_price_usd)),
        )
        self.conn.commit()

    def total_spend(self) -> tuple[float, float]:
        """(paid USD, list-price USD) summed over the spend log."""
        r = self.conn.execute(
            "SELECT COALESCE(SUM(cost_usd),0), COALESCE(SUM(list_price_usd),0) FROM spend"
        ).fetchone()
        return float(r[0]), float(r[1])

    def close(self) -> None:
        self.conn.close()

    def append(self, rec: GenerationRecord) -> None:
        row = rec.to_row()
        self.conn.execute(
            """INSERT OR REPLACE INTO generations
               (run_id, experiment_id, chain_id, repeat, generation, station_sequence, output_path,
                output_sha, clip_dist_to_g0, ssim_to_g0, cost_usd, list_price_usd, created_at, error, record)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rec.run_id,
                rec.experiment_id,
                rec.chain_id,
                rec.repeat,
                rec.generation,
                rec.station_sequence,
                rec.output_path,
                rec.output_sha,
                rec.metrics.clip_dist_to_g0,
                rec.metrics.ssim_to_g0,
                rec.cost_usd,
                rec.list_price_usd,
                rec.created_at,
                rec.error,
                json.dumps(row, sort_keys=True),
            ),
        )
        self.conn.commit()

    def has(self, chain_id: str, generation: int, repeat: int = 0) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM generations WHERE chain_id=? AND repeat=? AND generation=? AND error IS NULL",
            (chain_id, repeat, generation),
        )
        return cur.fetchone() is not None

    def get(self, chain_id: str, generation: int, repeat: int = 0) -> GenerationRecord | None:
        cur = self.conn.execute(
            "SELECT record FROM generations WHERE chain_id=? AND repeat=? AND generation=?",
            (chain_id, repeat, generation),
        )
        row = cur.fetchone()
        return GenerationRecord.from_row(json.loads(row["record"])) if row else None

    def chain(self, chain_id: str, repeat: int = 0) -> list[GenerationRecord]:
        cur = self.conn.execute(
            "SELECT record FROM generations WHERE chain_id=? AND repeat=? ORDER BY generation",
            (chain_id, repeat),
        )
        return [GenerationRecord.from_row(json.loads(r["record"])) for r in cur.fetchall()]

    def experiment(self, experiment_id: str) -> list[GenerationRecord]:
        cur = self.conn.execute(
            "SELECT record FROM generations WHERE experiment_id=? ORDER BY chain_id, repeat, generation",
            (experiment_id,),
        )
        return [GenerationRecord.from_row(json.loads(r["record"])) for r in cur.fetchall()]

    def all(self) -> list[GenerationRecord]:
        cur = self.conn.execute(
            "SELECT record FROM generations ORDER BY experiment_id, chain_id, repeat, generation"
        )
        return [GenerationRecord.from_row(json.loads(r["record"])) for r in cur.fetchall()]

    def chains(self, experiment_id: str | None = None) -> list[dict[str, Any]]:
        sql = """SELECT experiment_id, chain_id, repeat, station_sequence,
                        COUNT(*) AS generations, MAX(generation) AS last_generation,
                        SUM(cost_usd) AS cost_usd, SUM(list_price_usd) AS list_price_usd,
                        MIN(created_at) AS started, MAX(created_at) AS finished,
                        SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) AS errors
                 FROM generations"""
        args: tuple[Any, ...] = ()
        if experiment_id:
            sql += " WHERE experiment_id=?"
            args = (experiment_id,)
        sql += " GROUP BY experiment_id, chain_id, repeat ORDER BY experiment_id, chain_id, repeat"
        return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def experiments(self) -> list[dict[str, Any]]:
        sql = """SELECT experiment_id, COUNT(DISTINCT chain_id || '/' || repeat) AS chains, COUNT(*) AS generations,
                        SUM(cost_usd) AS cost_usd, SUM(list_price_usd) AS list_price_usd
                 FROM generations GROUP BY experiment_id ORDER BY experiment_id"""
        return [dict(r) for r in self.conn.execute(sql).fetchall()]

    def total_cost(self) -> tuple[float, float]:
        r = self.conn.execute(
            "SELECT COALESCE(SUM(cost_usd),0), COALESCE(SUM(list_price_usd),0) FROM generations"
        ).fetchone()
        return float(r[0]), float(r[1])

    def delete_chain(self, chain_id: str, repeat: int | None = None) -> int:
        if repeat is None:
            cur = self.conn.execute("DELETE FROM generations WHERE chain_id=?", (chain_id,))
        else:
            cur = self.conn.execute(
                "DELETE FROM generations WHERE chain_id=? AND repeat=?", (chain_id, repeat)
            )
        self.conn.commit()
        return cur.rowcount

    def save_results(self, experiment_id: str, path: Path) -> int:
        """Write every row of one experiment as sorted JSONL (chain, repeat, generation).

        The file is a snapshot of SQLite, written whole each time, so it never drifts from the
        database and is safe to commit. `import_jsonl` reads it back.
        """
        recs = self.experiment(experiment_id)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for rec in recs:
                f.write(json.dumps(rec.to_row(), sort_keys=True) + "\n")
        tmp.replace(path)
        return len(recs)

    def import_jsonl(self, path: Path) -> int:
        """Load a `save_results` file. Rows with the same key replace existing ones."""
        n = 0
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                self.append(GenerationRecord.from_row(json.loads(line)))
                n += 1
        return n

    def __iter__(self) -> Iterable[GenerationRecord]:
        return iter(self.all())
