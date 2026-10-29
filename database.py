from collections.abc import Mapping
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import declarative_base, sessionmaker


# =========================================================
# ENV FILE
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(
    dotenv_path=ENV_FILE,
    # Keep deployment-provided values authoritative over local defaults.
    override=False,
)


# =========================================================
# DATABASE CONFIG
# =========================================================

def build_database_url(environment: Mapping[str, str]) -> URL:
    # Accept a complete deployment URL without rebuilding or exposing credentials.
    configured_url = environment.get("DATABASE_URL")
    if configured_url:
        return make_url(configured_url)

    required_values = {
        key: environment.get(key)
        for key in ("DB_USERNAME", "DB_PASSWORD", "DB_NAME")
    }
    missing_values = [
        key for key, value in required_values.items() if not value
    ]
    if missing_values:
        raise ValueError(
            "Missing database configuration: "
            + ", ".join(missing_values)
            + ". Set DATABASE_URL or the DB_USERNAME, DB_PASSWORD, and "
            "DB_NAME variables in the process environment or root .env."
        )

    try:
        port = int(environment.get("DB_PORT", "5432"))
    except ValueError as error:
        raise ValueError("DB_PORT must be an integer") from error

    return URL.create(
        "postgresql+psycopg2",
        username=required_values["DB_USERNAME"],
        password=required_values["DB_PASSWORD"],
        host=environment.get("DB_HOST") or "localhost",
        port=port,
        database=required_values["DB_NAME"],
    )


DATABASE_URL = build_database_url(os.environ)


# =========================================================
# DATABASE ENGINE
# =========================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


# =========================================================
# DATABASE SESSION
# =========================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# =========================================================
# SQLALCHEMY BASE
# =========================================================

Base = declarative_base()