"""Store model"""
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, JSON, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import BaseModel
from .enums import POSSystem

if TYPE_CHECKING:
    from .product import Product
    from .search_log import SearchLog
    from .sales import SalesBaseline, SalesCurrent
    from .store_metrics import StoreMetrics

class Store(BaseModel):
    """Store entity representing a dispensary"""
    __tablename__ = "stores"
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    pos_type: Mapped[POSSystem] = mapped_column(default=POSSystem.POSABIT)
    pos_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    geo_lat: Mapped[Optional[float]] = mapped_column(Numeric(10, 8), nullable=True)
    geo_lon: Mapped[Optional[float]] = mapped_column(Numeric(11, 8), nullable=True)
    
    # Relationships
    products: Mapped[List["Product"]] = relationship(
        "Product", 
        back_populates="store",
        cascade="all, delete-orphan"
    )
    search_logs: Mapped[List["SearchLog"]] = relationship(
        "SearchLog",
        back_populates="store",
        cascade="all, delete-orphan"
    )
    sales_baseline: Mapped[List["SalesBaseline"]] = relationship(
        "SalesBaseline",
        back_populates="store",
        cascade="all, delete-orphan"
    )
    sales_current: Mapped[List["SalesCurrent"]] = relationship(
        "SalesCurrent",
        back_populates="store", 
        cascade="all, delete-orphan"
    )
    store_metrics: Mapped[List["StoreMetrics"]] = relationship(
        "StoreMetrics",
        back_populates="store",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Store(name='{self.name}', slug='{self.slug}')>"