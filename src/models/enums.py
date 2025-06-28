"""Enums for type safety across the application"""
from enum import Enum

class ProductFamily(str, Enum):
    """Official POSaBIT Product Family categories"""
    FLOWER = "flower"
    EDIBLE_LIQUID = "edible_liquid"
    EDIBLE_SOLID = "edible_solid"
    PREROLL = "preroll"
    TOPICAL = "topical"
    CONCENTRATE = "concentrate"
    CARTRIDGE = "cartridge"
    CBD = "cbd"
    APPAREL = "apparel"
    PARAPHERNALIA = "paraphernalia"
    SAMPLE = "sample"
    SEED = "seed"
    CLONE = "clone"
    OTHER = "other"

class StrainType(str, Enum):
    """Cannabis strain types"""
    INDICA = "indica"
    SATIVA = "sativa"
    HYBRID = "hybrid"
    CBD_DOMINANT = "cbd_dominant"
    UNKNOWN = "unknown"

class POSSystem(str, Enum):
    """Supported POS systems"""
    POSABIT = "posabit"
    COVA = "cova"
    DUTCHIE = "dutchie"
    FLOWHUB = "flowhub"
    TREEZ = "treez"
    BLAZE = "blaze"
    JANE = "jane"
    LEAFLY = "leafly"
    OTHER = "other"