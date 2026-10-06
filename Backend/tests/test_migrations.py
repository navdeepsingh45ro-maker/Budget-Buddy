"""Migrations must match the models and be safe on every kind of existing database.

Each test uses its own throwaway SQLite file and engine, never the shared test DB.
"""
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import migrations_runner  # noqa: E402
from alembic import command  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from database import Base  # noqa: E402


@pytest.fixture
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'migration-test.db'}")
    yield eng
    eng.dispose()


def _schema(eng):
    insp = inspect(eng)
    return {t: {c["name"] for c in insp.get_columns(t)} for t in insp.get_table_names() if t != "alembic_version"}


def _model_schema():
    return {name: {c.name for c in table.columns} for name, table in Base.metadata.tables.items()}


def _version(eng):
    with eng.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()


def _head():
    return ScriptDirectory.from_config(migrations_runner._alembic_config(None)).get_current_head()


def test_upgrade_empty_db_matches_models(engine):
    migrations_runner.run_migrations(engine)
    assert _schema(engine) == _model_schema()  # fails if a model changed without a migration
    assert _version(engine) == _head()


def test_indexes_and_unique_constraints_match_models(engine):
    migrations_runner.run_migrations(engine)
    insp = inspect(engine)
    for name, table in Base.metadata.tables.items():
        expected_indexes = {i.name for i in table.indexes}
        assert expected_indexes <= {i["name"] for i in insp.get_indexes(name)}, name
        expected_unique = {u.name for u in table.constraints if u.__class__.__name__ == "UniqueConstraint" and u.name}
        assert expected_unique <= {u["name"] for u in insp.get_unique_constraints(name)}, name


def test_existing_create_all_db_is_stamped_and_keeps_rows(engine):
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (name, email, password) VALUES ('Old User', 'old@example.com', 'hash')"))

    migrations_runner.run_migrations(engine)

    assert _version(engine) == _head()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT email FROM users")).scalars().all() == ["old@example.com"]
    assert _schema(engine) == _model_schema()


def test_old_db_missing_newest_table_gets_it_created(engine):
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE email_verifications"))
        conn.execute(text("INSERT INTO users (name, email, password) VALUES ('Old User', 'old@example.com', 'hash')"))

    migrations_runner.run_migrations(engine)

    assert "email_verifications" in inspect(engine).get_table_names()
    assert _version(engine) == _head()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar() == 1


def test_running_twice_is_harmless(engine):
    migrations_runner.run_migrations(engine)
    migrations_runner.run_migrations(engine)
    assert _version(engine) == _head()
    assert _schema(engine) == _model_schema()


def test_downgrade_to_base_then_upgrade_head(engine):
    migrations_runner.run_migrations(engine)
    cfg = migrations_runner._alembic_config(engine)

    command.downgrade(cfg, "base")
    assert _schema(engine) == {}

    command.upgrade(cfg, "head")
    assert _schema(engine) == _model_schema()
