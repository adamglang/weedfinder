"""Strain models"""
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from .base import BaseModel
from .enums import StrainType

if TYPE_CHECKING:
    from .product import Product

class Strain(BaseModel):
    """Strain entity representing a cannabis strain"""
    __tablename__ = "strains"
    
    canonical_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    cultivar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    strain_type: Mapped[StrainType] = mapped_column(default=StrainType.UNKNOWN)
    lineage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vector: Mapped[Optional[List[float]]] = mapped_column(Vector(768), nullable=True)
    
    # Relationships
    effects: Mapped[List["StrainEffect"]] = relationship(
        "StrainEffect",
        back_populates="strain",
        cascade="all, delete-orphan"
    )
    products: Mapped[List["Product"]] = relationship(
        "Product",
        back_populates="strain"
    )
    
    def __repr__(self) -> str:
        return f"<Strain(name='{self.canonical_name}', type='{self.strain_type}')>"

class StrainEffect(BaseModel):
    """Strain effect entity (many-to-many relationship)"""
    __tablename__ = "strain_effects"
    
    strain_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("strains.id", ondelete="CASCADE"),
        nullable=False
    )
    effect: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), default=1.0)
    
    # Relationships
    strain: Mapped["Strain"] = relationship("Strain", back_populates="effects")
    
    def __repr__(self) -> str:
        return f"<StrainEffect(effect='{self.effect}', confidence={self.confidence})>"