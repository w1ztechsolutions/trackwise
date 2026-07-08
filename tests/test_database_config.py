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
