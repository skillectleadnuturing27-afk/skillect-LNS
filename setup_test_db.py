
from sqlalchemy import create_engine
from models import Base
from database import engine as backend_engine

TEST_DB_NAME = "lead_db_test"

# Reuse the working backend credentials, but target only the test database.
test_url = backend_engine.url.set(database=TEST_DB_NAME)

test_engine = create_engine(
    test_url,
    pool_pre_ping=True,
)

try:
    with test_engine.connect() as connection:
        current_database = connection.exec_driver_sql(
            "SELECT current_database()"
        ).scalar()

        print("Connected database:", current_database)

        if current_database != TEST_DB_NAME:
            raise RuntimeError(
                "Wrong database. Stopping for safety."
            )

    Base.metadata.create_all(bind=test_engine)

    print("SUCCESS! Test database setup completed.")
    print("Tables:", list(Base.metadata.tables.keys()))

except Exception as error:
    print("DATABASE SETUP FAILED")
    print("Error:", error)

finally:
    test_engine.dispose()


