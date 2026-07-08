import importlib


def test_default_database_uri_reads_dotenv(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql://neon.example/neondb\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import config

    importlib.reload(config)

    uri = config._default_database_uri()
    assert uri.startswith("postgresql+psycopg://")
    assert "neon.example" in uri


def test_strip_channel_binding(monkeypatch, tmp_path):
    """channel_binding=require is a libpq param not supported by psycopg 3.x."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql://user:pass@neon.tech/db?sslmode=require&channel_binding=require\n"
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import config

    importlib.reload(config)

    uri = config._default_database_uri()
    assert "channel_binding" not in uri, f"channel_binding should be stripped: {uri}"
    assert "sslmode=require" in uri, f"sslmode should be preserved: {uri}"
    assert uri.startswith("postgresql+psycopg://")


def test_neon_pool_options(monkeypatch, tmp_path):
    """Neon URLs should get reduced pool settings."""
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql://user:pass@neon.tech/db\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import config

    importlib.reload(config)

    opts = config._get_pool_options(is_neon=True)
    assert opts["pool_size"] == 2
    assert opts["max_overflow"] == 3
    assert opts["pool_recycle"] == 120


def test_non_neon_pool_options():
    """Non-Neon URLs should get standard pool settings."""
    import config

    opts = config._get_pool_options(is_neon=False)
    assert opts["pool_size"] == 5
    assert opts["max_overflow"] == 10
    assert opts["pool_recycle"] == 300


def test_is_neon_detection():
    import config

    assert config._is_neon("postgresql://user:pass@neon.tech/db") is True
    assert config._is_neon("postgresql://user:pass@example.com/db") is False
    assert config._is_neon(None) is False