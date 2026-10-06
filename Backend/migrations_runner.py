"""Database migrations: brings the database schema up to date when the server starts.

HOW TO CHANGE THE DATABASE SCHEMA FROM NOW ON
---------------------------------------------
Never edit tables by hand and never rely on create_all for changes to tables
that already exist (it only creates missing tables, it never alters them).
Instead:

  1. Edit the model in models/ (add a column, change a length, ...). A brand
     new model file must also be imported in models/__init__.py.
  2. From the Backend folder run:
         alembic revision --autogenerate -m "short description of the change"
     (set DATABASE_URL to a throwaway SQLite file first so you never point it
     at real data; autogenerate only needs a database that is already at head,
     e.g. one created by running the app once).
  3. Open the new file in alembic/versions/ and READ it. Autogenerate is a
     draft: check it does what you meant (it cannot tell a rename from a
     drop + add, and new NOT NULL columns on tables with data need a default).
  4. Commit the model change and the new migration file together.
  5. Done. The migration is applied automatically on the next server start,
     locally and in production, so no manual step on the live database.

tests/test_migrations.py fails if a model changed but no migration was added.

WHAT run_migrations() DOES AT STARTUP
-------------------------------------
  a) Empty database                       -> alembic upgrade head (creates everything).
  b) Has the app's tables but no
     alembic_version table (made earlier
     by create_all, e.g. the local
     database.db)                         -> create any table still missing, then
                                             alembic stamp head. Existing rows are
                                             never touched.
  c) Already under Alembic                -> alembic upgrade head.

On Postgres a pg_advisory_lock makes sure only one process migrates at a time
(two server instances starting together); the other waits, then finds nothing to do.
"""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

import database
import models  # noqa: F401  (registers every model on Base.metadata)

# Own handler so the one-line summary shows up in the server output even though
# the app does not configure logging itself.
logger = logging.getLogger("migrations")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
    logger.addHandler(_handler)
    logger.propagate = False

BACKEND_DIR = Path(__file__).resolve().parent
# Arbitrary constant shared by every process that migrates this app's database.
_ADVISORY_LOCK_KEY = 7_424_001


def _alembic_config(engine: Engine) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["engine"] = engine  # alembic/env.py uses this instead of database.engine
    cfg.attributes["from_runner"] = True  # keep the app's logging setup untouched
    return cfg


def _migrate(engine: Engine) -> str:
    """Do the work for whichever of the three situations applies; return a one-line summary."""
    cfg = _alembic_config(engine)
    head = ScriptDirectory.from_config(cfg).get_current_head()
    existing = set(inspect(engine).get_table_names())
    app_tables = set(database.Base.metadata.tables)

    if "alembic_version" in existing:
        command.upgrade(cfg, "head")
        return f"database already under Alembic, upgraded to head ({head})"

    if not existing & app_tables:
        command.upgrade(cfg, "head")
        return f"empty database, created schema with Alembic (head {head})"

    # Created by create_all before migrations existed. Older copies may lack the
    # newest tables, so add whatever is missing, then record that it is at head.
    missing = sorted(app_tables - existing)
    database.Base.metadata.create_all(bind=engine, checkfirst=True)
    # create_all never adds columns to a table that already exists; flag any gap
    # so it is fixed by hand instead of silently stamping a mismatched schema.
    insp = inspect(engine)
    for name, table in database.Base.metadata.tables.items():
        gap = {c.name for c in table.columns} - {c["name"] for c in insp.get_columns(name)}
        if gap:
            logger.warning("Table %s is missing column(s) %s; add them with a migration", name, sorted(gap))
    command.stamp(cfg, "head")
    return (
        f"existing database without Alembic, created {len(missing)} missing table(s)"
        f"{' (' + ', '.join(missing) + ')' if missing else ''} and stamped head ({head})"
    )


def run_migrations(engine: Engine | None = None) -> None:
    """Bring the schema up to date. `engine` defaults to the app's engine (tests pass their own)."""
    engine = engine or database.engine

    if engine.dialect.name == "postgresql":
        # Session-level lock on its own connection, held for the whole migration.
        with engine.connect() as lock_conn:
            lock_conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _ADVISORY_LOCK_KEY})
            lock_conn.commit()
            try:
                summary = _migrate(engine)
            finally:
                lock_conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _ADVISORY_LOCK_KEY})
                lock_conn.commit()
    else:
        summary = _migrate(engine)

    logger.info("Migrations: %s", summary)
