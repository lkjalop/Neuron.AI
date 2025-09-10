import os, time, sqlite3, tempfile

# NOTE: We set SQLITE_DB_PATH before importing prune_retrieval_chunks so module-level path resolves correctly.



def _init_db(path: str):
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS retrieval_chunks (id TEXT PRIMARY KEY, doc TEXT, chunk_id INT, hash TEXT, text TEXT, length INT, tenant TEXT, created_ts REAL)")
    now = time.time()
    # Insert 6 rows: 3 fresh, 3 old
    rows = []
    for i in range(3):
        rows.append((f"fresh_{i}", "DOC", i, f"h{i}", "text", 4, "t1", now - 100))
    for i in range(3):
        rows.append((f"old_{i}", "DOC", i+10, f"h_old{i}", "text", 4, "t1", now - (4000 * 3600)))  # way older than any threshold
    cur.executemany("INSERT OR REPLACE INTO retrieval_chunks VALUES (?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


def test_prune_retrieval_chunks_age_and_cap(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, 'retention.db')
        monkeypatch.setenv('SQLITE_DB_PATH', db_path)
        _init_db(db_path)
        # Import after env set to ensure module sees path
        from importlib import reload
        import core.retrieval.retention as retention_mod  # type: ignore
        reload(retention_mod)
        # Execute prune: max_age_hours=1 should remove old rows (age ~4000h)
        res = retention_mod.prune_retrieval_chunks(max_rows=2, max_age_hours=1)
        # Validate age purge removed at least the 3 old rows
        assert res['purged_age'] >= 3, res
        # Capacity should then trim to at most 2 rows
        assert res['remaining_rows'] <= 2, res
        # A second run should be idempotent (no further deletions)
        res2 = retention_mod.prune_retrieval_chunks(max_rows=2, max_age_hours=1)
        assert res2['purged_age'] == 0, res2
        assert res2['purged_rows'] == 0, res2
        assert res2['remaining_rows'] == res['remaining_rows']
