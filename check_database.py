from database import SessionLocal
from sqlalchemy import text


db = SessionLocal()

try:
    result = db.execute(
        text("""
            SELECT
                current_database() AS database,
                current_user AS db_user,
                inet_server_addr() AS server_ip,
                inet_server_port() AS server_port,
                current_setting('data_directory') AS data_directory
        """)
    ).mappings().first()

    lead_count = db.execute(
        text("""
            SELECT COUNT(*)
            FROM public.leads
        """)
    ).scalar()

    lead_ids = db.execute(
        text("""
            SELECT id
            FROM public.leads
            ORDER BY id
        """)
    ).scalars().all()

    print()
    print("=" * 60)
    print("BACKEND DATABASE CHECK")
    print("=" * 60)

    print("Database       :", result["database"])
    print("User           :", result["db_user"])
    print("Server IP      :", result["server_ip"])
    print("Server Port    :", result["server_port"])
    print("Data Directory :", result["data_directory"])
    print("Lead Count     :", lead_count)
    print("Lead IDs       :", lead_ids)

    print("=" * 60)

finally:
    db.close()