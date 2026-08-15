"""
Shared fixtures for all tests.

Uses a temporary file-based SQLite database by default. Set TEST_DATABASE_URL to
run the same suite against a disposable PostgreSQL database; this deliberately
does not reuse a developer's ordinary DATABASE_URL.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# Create a temp file DB that persists for the test session unless CI explicitly
# supplies a disposable PostgreSQL database.
_configured_test_database_url = os.environ.get("TEST_DATABASE_URL")
_tempdb = None
if _configured_test_database_url:
    os.environ["DATABASE_URL"] = _configured_test_database_url
else:
    _tempdb = tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir="/tmp")  # noqa: SIM115
    os.environ["DATABASE_URL"] = f"sqlite:///{_tempdb.name}"

# Import after env is set — SQLAlchemy will use SQLite
from app import app  # noqa: E402
from db.models import Base, User  # noqa: E402

# Disable rate limiting during tests
app.config["TESTING"] = True


@pytest.fixture(scope="session")
def _test_db():
    """Create tables once per session, clean up at the very end."""
    from sqlalchemy import create_engine

    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()
    import contextlib

    if _tempdb is not None:
        with contextlib.suppress(Exception):
            os.unlink(_tempdb.name)


@pytest.fixture
def client():
    """Flask test client."""
    with app.test_client() as client:
        yield client


@pytest.fixture
def with_db(_test_db):
    """Yields a fresh engine for use in tests (tables already created)."""
    from sqlalchemy import create_engine

    engine = create_engine(os.environ["DATABASE_URL"])
    yield engine


@pytest.fixture
def admin_user(with_db):
    """Create an admin user in the test DB."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(os.environ["DATABASE_URL"])
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(email="admin@test.com", role="admin")
    session.add(user)
    session.commit()
    user_id = user.id
    session.close()
    return user_id


@pytest.fixture
def member_user(with_db):
    """Create a member user in the test DB."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(os.environ["DATABASE_URL"])
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(email="member@test.com", role="member")
    session.add(user)
    session.commit()
    user_id = user.id
    session.close()
    return user_id


@pytest.fixture
def reader_user(with_db):
    """Create a reader user in the test DB."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(os.environ["DATABASE_URL"])
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(email="reader@test.com", role="reader")
    session.add(user)
    session.commit()
    user_id = user.id
    session.close()
    return user_id


@pytest.fixture
def mock_ollama_response():
    """Mock Ollama responses for summarization and chat."""
    with (
        patch.dict(os.environ, {"VLLM_GEN_HOST": "localhost"}),
        patch("summarizer_v2._USE_VLLM", True),
        patch("summarizer_v2._get_llm_url", return_value="http://localhost:8000"),
        patch("summarizer_v2._OpenAI") as mock_openai_cls,
    ):
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content="Mock response"))]
        mock_client.chat.completions.create.return_value = mock_completion
        mock_openai_cls.return_value = mock_client

        yield


def _mock_generate(model_name, prompt, client=None):
    return f"Generated response for {model_name}"
