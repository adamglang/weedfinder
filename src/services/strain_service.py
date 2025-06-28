"""Strain service with custom business logic"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from .base_crud import BaseCRUDService
from ..models.strain import Strain, StrainEffect
from ..models.enums import StrainType

class StrainService(BaseCRUDService[Strain]):
    """Strain service with custom methods"""
    
    def __init__(self):
        super().__init__(Strain)
    
    def get_by_name(self, db: Session, canonical_name: str) -> Optional[Strain]:
        """Get strain by canonical name"""
        return self.find_by(db, canonical_name=canonical_name)
    
    def get_by_type(self, db: Session, strain_type: StrainType) -> List[Strain]:
        """Get strains by type"""
        return self.find_all_by(db, strain_type=strain_type)
    
    def upsert_strain(
        self,
        db: Session,
        canonical_name: str,
        strain_type: StrainType = StrainType.UNKNOWN,
        effects: List[str] = None,
        lineage: str = None,
        vector: List[float] = None
    ) -> Strain:
        """Insert or update strain with effects"""
        # Check if strain exists
        existing = self.get_by_name(db, canonical_name)
        
        strain_data = {
            "canonical_name": canonical_name,
            "strain_type": strain_type,
            "lineage": lineage,
            "vector": vector
        }
        
        if existing:
            strain = self.update(db, db_obj=existing, obj_in=strain_data)
        else:
            strain = self.create(db, obj_in=strain_data)
        
        # Handle effects
        if effects:
            self._update_strain_effects(db, strain.id, effects)
        
        return strain
    
    def _update_strain_effects(self, db: Session, strain_id: UUID, effects: List[str]):
        """Update strain effects (replace existing)"""
        # Remove existing effects
        db.query(StrainEffect).filter(StrainEffect.strain_id == strain_id).delete()
        
        # Add new effects
        for effect in effects:
            effect_obj = StrainEffect(
                strain_id=strain_id,
                effect=effect,
                confidence=1.0
            )
            db.add(effect_obj)
        
        db.commit()
    
    def add_effect(
        self,
        db: Session,
        strain_id: UUID,
        effect: str,
        confidence: float = 1.0
    ) -> StrainEffect:
        """Add a single effect to a strain"""
        effect_obj = StrainEffect(
            strain_id=strain_id,
            effect=effect,
            confidence=confidence
        )
        db.add(effect_obj)
        db.commit()
        db.refresh(effect_obj)
        return effect_obj
    
    def get_strains_by_effect(self, db: Session, effect: str) -> List[Strain]:
        """Get strains that have a specific effect"""
        return db.query(Strain).join(StrainEffect).filter(
            StrainEffect.effect == effect
        ).all()
    
    def search_strains_by_effects(
        self,
        db: Session,
        effects: List[str],
        strain_type: StrainType = None,
        match_all: bool = False
    ) -> List[Strain]:
        """Search strains by multiple effects"""
        query = db.query(Strain).join(StrainEffect)
        
        if match_all:
            # Must have ALL effects
            for effect in effects:
                query = query.filter(
                    Strain.id.in_(
                        db.query(StrainEffect.strain_id).filter(
                            StrainEffect.effect == effect
                        )
                    )
                )
        else:
            # Must have ANY of the effects
            query = query.filter(StrainEffect.effect.in_(effects))
        
        if strain_type:
            query = query.filter(Strain.strain_type == strain_type)
        
        return query.distinct().all()

class StrainEffectService(BaseCRUDService[StrainEffect]):
    """Strain effect service"""
    
    def __init__(self):
        super().__init__(StrainEffect)
    
    def get_effects_by_strain(self, db: Session, strain_id: UUID) -> List[StrainEffect]:
        """Get all effects for a strain"""
        return self.find_all_by(db, strain_id=strain_id)
    
    def get_unique_effects(self, db: Session) -> List[str]:
        """Get all unique effect names"""
        results = db.query(StrainEffect.effect).distinct().all()
        return [result[0] for result in results]

# Create singleton instances
strain_service = StrainService()
strain_effect_service = StrainEffectService()