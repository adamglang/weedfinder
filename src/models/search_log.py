"""Search log model"""
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Text, Integer, Boolean, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import BaseModel

if TYPE_CHECKING:
    from .store import Store

class SearchLog(BaseModel):
    """Search log entity for analytics"""
    __tablename__ = "search_logs"
    
    store_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id"),
        nullable=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    intent_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    results_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    store: Mapped[Optional["Store"]] = relationship("Store", back_populates="search_logs")
    
    def __repr__(self) -> str:
        return f"<SearchLog(query='{self.query[:50]}...', results={self.results_count})>"