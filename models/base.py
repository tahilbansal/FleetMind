import uuid
from sqlalchemy import Column, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# ---------------------------------------------------------------------------
# Helper — UUID primary key that works on both SQLite and PostgreSQL
# ---------------------------------------------------------------------------
def uuid_pk():
    return Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))