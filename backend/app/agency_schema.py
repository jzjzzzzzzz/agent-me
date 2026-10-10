"""Local tool tables; definitions are static and cannot come from source text."""


def extend_agency(db):
    db.execute(
        "CREATE TABLE IF NOT EXISTS tool_permissions "
        "(name TEXT PRIMARY KEY,data_json TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS action_plans (id TEXT PRIMARY KEY,"
        "idempotency_key TEXT UNIQUE NOT NULL,data_json TEXT NOT NULL)"
    )
    for table in ("tasks", "notes", "action_events"):
        db.execute(
            f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY,data_json TEXT NOT NULL)"
        )
