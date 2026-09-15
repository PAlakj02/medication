"""Shared pytest fixtures.

Two DB fixtures, deliberately pointed at two different databases:

- db_session: the isolated "_test"-suffixed database (same server, empty
  except for migrations). Use for ordinary unit/integration tests that
  create their own fixture rows — once real bulk data (RxNorm, DDInter,
  ...) is loaded into the dev DB, a test asserting a specific name doesn't
  already exist (e.g. "Diphenhydramine Hydrochloride") would spuriously
  collide with real rows there. Run migrations against the test DB before
  running tests: see the test DB setup note in README/CI config.

- dev_db_session: the actual dev/ingest database from app.db.engine
  (DATABASE_URL) — for tests that deliberately assert against real loaded
  data (tests/test_golden_interactions.py, tests/findings/
  test_source_gap_real_data.py). These skip with a clear message if the
  bulk pipeline (scripts/run_ingest.py) hasn't been run. Still wrapped in
  a rolled-back transaction for safety even though these tests are
  expected to be read-only.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import engine as _dev_engine

_settings = get_settings()
_base_url, _, _db_name = _settings.database_url.rpartition("/")
_test_database_url = f"{_base_url}/{_db_name}_test"
_test_engine = create_engine(_test_database_url, pool_pre_ping=True)


@pytest.fixture
def db_session():
    connection = _test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def dev_db_session():
    connection = _dev_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
