"""Store metrics model for ROI tracking"""
from typing import TYPE_CHECKING
from sqlalchemy import Date, Numeric, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date as date_type
from .base import BaseModel

if TYPE_CHECKING:
    from .store import Store

class StoreMetrics(BaseModel):
    """Store metrics entity for ROI calculation"""
    __tablename__ = "store_metrics"
    
    store_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id"),
        nullable=False
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    baseline_aov: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    current_aov: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    lift_abs: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    lift_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    searches_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    store: Mapped["Store"] = relationship("Store", back_populates="store_metrics")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('store_id', 'date', name='uq_store_date'),
    )
    
    def __repr__(self) -> str:
        return f"<StoreMetrics(date={self.date}, lift_pct={self.lift_pct}%)>"