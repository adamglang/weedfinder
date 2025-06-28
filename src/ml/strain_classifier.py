import openai
import json
import logging
from typing import List, Dict
import os
from ..models.enums import StrainType
from ..services import StrainService, StrainEffectService
from ..database.config import get_session

logger = logging.getLogger(__name__)

class StrainClassifier:
    """Classify cannabis strains using LLM to extract effects and attributes"""
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.strain_service = StrainService()
        self.strain_effect_service = StrainEffectService()
    
    def classify_strain(self, strain_name: str, additional_context: str = "") -> Dict:
        """Classify a single strain and return effects and attributes"""
        try:
            prompt = f"""You are a cannabis sommelier and expert. Analyze the strain "{strain_name}" and provide information in JSON format.

Additional context: {additional_context}

Return a JSON object with this exact structure:
{{
    "strain_type": "indica" | "sativa" | "hybrid" | "cbd_dominant",
    "effects": ["effect1", "effect2", "effect3", "effect4"],
    "medical_uses": ["use1", "use2", "use3"],
    "flavors": ["flavor1", "flavor2", "flavor3"],
    "confidence": 0.8
}}

Guidelines:
- effects: 3-4 primary effects (e.g., "relaxation", "euphoria", "focus", "creativity", "pain_relief", "sleep", "energy", "appetite")
- medical_uses: 2-3 medical applications (e.g., "anxiety", "insomnia", "chronic_pain", "depression", "nausea")
- flavors: 2-3 dominant flavors/aromas (e.g., "citrus", "earthy", "sweet", "pine", "berry", "diesel")
- confidence: your confidence level in this classification (0.0-1.0)
- Use only single words or simple phrases for each array item
- Base your response on known characteristics of this strain"""

            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo-0125",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=500
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validate and clean the response
            validated_result = {
                'strain_type': result.get('strain_type', 'hybrid'),
                'effects': result.get('effects', [])[:4],  # Limit to 4 effects
                'medical_uses': result.get('medical_uses', [])[:3],  # Limit to 3 uses
                'flavors': result.get('flavors', [])[:3],  # Limit to 3 flavors
                'confidence': min(max(result.get('confidence', 0.5), 0.0), 1.0)  # Clamp 0-1
            }
            
            logger.info(f"Classified strain '{strain_name}': {validated_result['strain_type']} with {len(validated_result['effects'])} effects")
            return validated_result
            
        except Exception as e:
            logger.error(f"Error classifying strain '{strain_name}': {e}")
            # Return default classification
            return {
                'strain_type': 'hybrid',
                'effects': ['relaxation'],
                'medical_uses': ['stress'],
                'flavors': ['earthy'],
                'confidence': 0.1
            }
    
    def classify_and_store_strain(self, strain_name: str, additional_context: str = "") -> str:
        """Classify a strain and store it in the database"""
        with get_session() as session:
            try:
                # Check if strain already exists
                existing_strain = self.strain_service.get_by_name(session, strain_name)
                if existing_strain:
                    logger.info(f"Strain '{strain_name}' already exists in database")
                    return str(existing_strain.id)
                
                # Classify the strain
                classification = self.classify_strain(strain_name, additional_context)
                
                # Map string strain type to enum
                strain_type_map = {
                    'indica': StrainType.INDICA,
                    'sativa': StrainType.SATIVA,
                    'hybrid': StrainType.HYBRID,
                    'cbd_dominant': StrainType.CBD_DOMINANT
                }
                strain_type = strain_type_map.get(classification['strain_type'], StrainType.HYBRID)
                
                # Store strain in database using service
                strain = self.strain_service.upsert_strain(
                    session,
                    canonical_name=strain_name,
                    strain_type=strain_type
                )
                
                # Store primary effects
                for effect in classification['effects']:
                    self.strain_effect_service.create(session, obj_in={
                        'strain_id': strain.id,
                        'effect': effect,
                        'confidence': classification['confidence']
                    })
                
                # Store medical uses with prefix
                for use in classification['medical_uses']:
                    self.strain_effect_service.create(session, obj_in={
                        'strain_id': strain.id,
                        'effect': f"medical_{use}",
                        'confidence': classification['confidence']
                    })
                
                # Store flavors with prefix
                for flavor in classification['flavors']:
                    self.strain_effect_service.create(session, obj_in={
                        'strain_id': strain.id,
                        'effect': f"flavor_{flavor}",
                        'confidence': classification['confidence']
                    })
                
                session.commit()
                logger.info(f"Successfully classified and stored strain '{strain_name}' with ID {strain.id}")
                return str(strain.id)
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error classifying and storing strain '{strain_name}': {e}")
                raise
    
    def batch_classify_strains(self, strain_names: List[str]) -> Dict[str, str]:
        """Classify multiple strains in batch"""
        results = {}
        
        for strain_name in strain_names:
            try:
                strain_id = self.classify_and_store_strain(strain_name)
                results[strain_name] = strain_id
            except Exception as e:
                logger.error(f"Failed to classify strain '{strain_name}': {e}")
                results[strain_name] = None
        
        logger.info(f"Batch classified {len([r for r in results.values() if r])} out of {len(strain_names)} strains")
        return results
    
    def get_strain_effects(self, strain_id: str) -> Dict:
        """Get all effects and attributes for a strain"""
        with get_session() as session:
            try:
                # Get basic strain info
                strain = self.strain_service.get(session, strain_id)
                if not strain:
                    return {}
                
                # Get all effects for this strain
                strain_effects = self.strain_effect_service.find_all_by(session, strain_id=strain_id)
                
                # Categorize effects
                effects = []
                medical_uses = []
                flavors = []
                
                for effect_obj in strain_effects:
                    effect = effect_obj.effect
                    if effect.startswith('medical_'):
                        medical_uses.append(effect.replace('medical_', ''))
                    elif effect.startswith('flavor_'):
                        flavors.append(effect.replace('flavor_', ''))
                    else:
                        effects.append(effect)
                
                return {
                    'name': strain.name,
                    'strain_type': strain.strain_type.value,
                    'effects': effects,
                    'medical_uses': medical_uses,
                    'flavors': flavors
                }
                
            except Exception as e:
                logger.error(f"Error getting strain effects for {strain_id}: {e}")
                return {}
    
    def update_strain_classification(self, strain_name: str, force_reclassify: bool = False) -> str:
        """Update an existing strain's classification"""
        with get_session() as session:
            try:
                existing_strain = self.strain_service.get_by_name(session, strain_name)
                
                if not existing_strain:
                    # Strain doesn't exist, classify and store
                    return self.classify_and_store_strain(strain_name)
                
                strain_id = str(existing_strain.id)
                
                if force_reclassify:
                    # Delete existing effects
                    existing_effects = self.strain_effect_service.find_all_by(session, strain_id=existing_strain.id)
                    for effect in existing_effects:
                        self.strain_effect_service.delete(session, effect.id)
                    
                    # Reclassify
                    classification = self.classify_strain(strain_name)
                    
                    # Map string strain type to enum
                    strain_type_map = {
                        'indica': StrainType.INDICA,
                        'sativa': StrainType.SATIVA,
                        'hybrid': StrainType.HYBRID,
                        'cbd_dominant': StrainType.CBD_DOMINANT
                    }
                    strain_type = strain_type_map.get(classification['strain_type'], StrainType.HYBRID)
                    
                    # Update strain type
                    self.strain_service.update(session, db_obj=existing_strain, obj_in={'strain_type': strain_type})
                    
                    # Store new effects
                    for effect in classification['effects']:
                        self.strain_effect_service.create(session, obj_in={
                            'strain_id': existing_strain.id,
                            'effect': effect,
                            'confidence': classification['confidence']
                        })
                    
                    session.commit()
                    logger.info(f"Reclassified strain '{strain_name}'")
                
                return strain_id
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error updating strain classification for '{strain_name}': {e}")
                raise

def test_strain_classifier():
    """Test the strain classifier"""
    classifier = StrainClassifier()
    
    # Test single strain classification
    test_strains = ["Blue Dream", "OG Kush", "Girl Scout Cookies", "Sour Diesel"]
    
    for strain in test_strains:
        print(f"\nTesting classification for: {strain}")
        try:
            result = classifier.classify_strain(strain)
            print(f"Result: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_strain_classifier()