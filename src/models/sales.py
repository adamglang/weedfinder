"""Sales models for ROI tracking"""
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Numeric, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from .base import BaseModel

if TYPE_CHECKING:
    from .store import Store

class SalesBaseline(BaseModel):
    """Sales baseline data for ROI calculation"""
    __tablename__ = "sales_baseline"
    
    store_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id"),
        nullable=False
    )
    ticket_id: Mapped[str] = mapped_column(String(255), nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    store: Mapped["Store"] = relationship("Store", back_populates="sales_baseline")
    
    def __repr__(self) -> str:
        return f"<SalesBaseline(ticket_id='{self.ticket_id}', subtotal=${self.subtotal})>"

class SalesCurrent(BaseModel):
    """Current sales data for ROI calculation"""
    __tablename__ = "sales_current"
    
    store_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id"),
        nullable=False
    )
    ticket_id: Mapped[str] = mapped_column(String(255), nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    item_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # for WF_UPSELL tags
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    store: Mapped["Store"] = relationship("Store", back_populates="sales_current")
    
    def __repr__(self) -> str:
        return f"<SalesCurrent(ticket_id='{self.ticket_id}', subtotal=${self.subtotal})>"