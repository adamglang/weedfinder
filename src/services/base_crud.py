"""Generic CRUD service base class - similar to Spring Boot repositories"""
from typing import TypeVar, Generic, Type, List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ..models.base import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)

class BaseCRUDService(Generic[ModelType]):
    """Generic CRUD service for database operations"""
    
    def __init__(self, model: Type[ModelType]):
        self.model = model
    
    def create(self, db: Session, *, obj_in: Dict[str, Any]) -> ModelType:
        """Create a new entity"""
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get(self, db: Session, id: UUID) -> Optional[ModelType]:
        """Get entity by ID"""
        return db.query(self.model).filter(self.model.id == id).first()
    
    def list(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None
    ) -> List[ModelType]:
        """List entities with pagination and filtering (alias for get_multi)"""
        return self.get_multi(db, skip=skip, limit=limit, filters=filters, order_by=order_by)
    
    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None
    ) -> List[ModelType]:
        """Get multiple entities with pagination and filtering"""
        query = db.query(self.model)
        
        # Apply filters
        if filters:
            filter_conditions = []
            for key, value in filters.items():
                if hasattr(self.model, key):
                    if isinstance(value, list):
                        filter_conditions.append(getattr(self.model, key).in_(value))
                    else:
                        filter_conditions.append(getattr(self.model, key) == value)
            
            if filter_conditions:
                query = query.filter(and_(*filter_conditions))
        
        # Apply ordering
        if order_by and hasattr(self.model, order_by):
            query = query.order_by(getattr(self.model, order_by))
        
        return query.offset(skip).limit(limit).all()
    
    def update(
        self, 
        db: Session, 
        *, 
        db_obj: ModelType, 
        obj_in: Dict[str, Any]
    ) -> ModelType:
        """Update an existing entity"""
        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def delete(self, db: Session, *, id: UUID) -> Optional[ModelType]:
        """Delete entity by ID"""
        obj = db.query(self.model).get(id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj
    
    def count(self, db: Session, *, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities with optional filters"""
        query = db.query(self.model)
        
        if filters:
            filter_conditions = []
            for key, value in filters.items():
                if hasattr(self.model, key):
                    if isinstance(value, list):
                        filter_conditions.append(getattr(self.model, key).in_(value))
                    else:
                        filter_conditions.append(getattr(self.model, key) == value)
            
            if filter_conditions:
                query = query.filter(and_(*filter_conditions))
        
        return query.count()
    
    def exists(self, db: Session, *, filters: Dict[str, Any]) -> bool:
        """Check if entity exists with given filters"""
        return self.count(db, filters=filters) > 0
    
    def find_by(self, db: Session, **kwargs) -> Optional[ModelType]:
        """Find single entity by arbitrary fields"""
        filter_conditions = []
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                filter_conditions.append(getattr(self.model, key) == value)
        
        if not filter_conditions:
            return None
            
        return db.query(self.model).filter(and_(*filter_conditions)).first()
    
    def find_all_by(self, db: Session, **kwargs) -> List[ModelType]:
        """Find all entities by arbitrary fields (no pagination)"""
        filter_conditions = []
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                if isinstance(value, list):
                    filter_conditions.append(getattr(self.model, key).in_(value))
                else:
                    filter_conditions.append(getattr(self.model, key) == value)
        
        if not filter_conditions:
            return []
            
        return db.query(self.model).filter(and_(*filter_conditions)).all()
    
    def upsert(
        self, 
        db: Session, 
        *, 
        obj_in: Dict[str, Any],
        unique_fields: List[str]
    ) -> ModelType:
        """Insert or update based on unique fields"""
        # Build filter for existing record
        filters = {field: obj_in[field] for field in unique_fields if field in obj_in}
        existing = self.find_by(db, **filters)
        
        if existing:
            return self.update(db, db_obj=existing, obj_in=obj_in)
        else:
            return self.create(db, obj_in=obj_in)