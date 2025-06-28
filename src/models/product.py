"""Product model"""
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Numeric, Integer, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import BaseModel
from .enums import ProductFamily

if TYPE_CHECKING:
    from .store import Store
    from .strain import Strain

class Product(BaseModel):
    """Product entity representing a cannabis product in a store"""
    __tablename__ = "products"
    
    store_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False
    )
    strain_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("strains.id"),
        nullable=True
    )
    sku: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    product_family: Mapped[ProductFamily] = mapped_column(default=ProductFamily.OTHER)
    thc_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    cbd_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    json_raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Relationships
    store: Mapped["Store"] = relationship("Store", back_populates="products")
    strain: Mapped[Optional["Strain"]] = relationship("Strain", back_populates="products")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('store_id', 'sku', name='uq_store_sku'),
    )
    
    def __repr__(self) -> str:
        return f"<Product(name='{self.name}', sku='{self.sku}', price=${self.price})>"