"""Static owner-control schema extension, applied in the migration transaction."""


def extend_control(db):
    db.execute("INSERT OR IGNORE INTO workspace VALUES ('learning_policy','{}')")
    db.execute("INSERT OR IGNORE INTO workspace VALUES ('learning_revision','1')")
    db.execute(
        "CREATE TABLE IF NOT EXISTS consolidation_plans "
        "(id TEXT PRIMARY KEY,data_json TEXT NOT NULL)"
    )
    for table in ("audit_events", "import_archives"):
        db.execute(
            f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY,data_json TEXT NOT NULL)"
        )
