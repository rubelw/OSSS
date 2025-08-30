# src/OSSS/db/models/google_accounts.py
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from OSSS.db.base import Base, UUIDMixin, JSONB

class GoogleAccount(UUIDMixin, Base):
    __tablename__ = "google_accounts"

    user_id = mapped_column(sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    # store tokens + scopes (encrypt these fields in prod)
    access_token = mapped_column(sa.Text, nullable=False)
    refresh_token = mapped_column(sa.Text, nullable=True)
    token_uri = mapped_column(sa.Text, nullable=False, default="https://oauth2.googleapis.com/token")
    client_id = mapped_column(sa.Text, nullable=False)
    client_secret = mapped_column(sa.Text, nullable=False)
    expiry = mapped_column(sa.DateTime(timezone=True), nullable=True)
    scopes = mapped_column(JSONB, nullable=True)

    created_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
