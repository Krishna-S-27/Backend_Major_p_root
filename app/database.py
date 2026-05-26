"""
SQLAlchemy database configuration
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

# ===================== DATABASE CONFIGURATION =====================

# MySQL connection string
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'mysql+pymysql://root:@localhost:3306/violence_detection_db'
)

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    pool_recycle=3600,
    pool_pre_ping=True,
    connect_args={'charset': 'utf8mb4'}
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

# Base class for models
Base = declarative_base()

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database (create tables)"""
    Base.metadata.create_all(bind=engine)
    ensure_schema_columns()


def ensure_schema_columns():
    """Add columns needed by newer app versions to existing databases."""
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        return

    existing_user_columns = {column["name"] for column in inspector.get_columns("users")}
    user_columns = {
        "phone": "VARCHAR(20)",
        "emergency_phone": "VARCHAR(20)",
        "emergency_email": "VARCHAR(100)",
        "drive_folder_id": "VARCHAR(255)",
    }

    with engine.begin() as connection:
        for column_name, column_type in user_columns.items():
            if column_name not in existing_user_columns:
                connection.execute(
                    text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
                )

    if not inspector.has_table("user_profiles"):
        return

    existing_profile_columns = {
        column["name"] for column in inspector.get_columns("user_profiles")
    }
    if "google_drive_folder_id" not in existing_profile_columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE user_profiles ADD COLUMN google_drive_folder_id VARCHAR(255)")
            )

    if inspector.has_table("incidents"):
        incident_columns = {column["name"]: column for column in inspector.get_columns("incidents")}
        upload_status_column = incident_columns.get("upload_status")
        if upload_status_column is not None:
            column_type = upload_status_column["type"]
            try:
                enums = column_type.enums
            except AttributeError:
                enums = []

            if "LOCAL" not in enums:
                enum_values = ",".join([f"'{value}'" for value in enums + ["LOCAL"]])
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            f"ALTER TABLE incidents MODIFY COLUMN upload_status ENUM({enum_values}) DEFAULT 'PENDING'"
                        )
                    )
