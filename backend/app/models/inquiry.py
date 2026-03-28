from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class Inquiry(Base):
    __tablename__ = "inquiries"

    id = Column(String, primary_key=True)
    tenant = Column(String, nullable=False, index=True)

    asset_type = Column(String, nullable=False)
    location = Column(String, nullable=False)
    problem = Column(Text, nullable=False)

    contact_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
