import openai
import json
import logging
from typing import List, Dict, Optional
import os
from .database import get_db_cursor, upsert_strain

logger = logging.getLogger(__name__)

class StrainClassifier:
    """Classify cannabis strains using LLM to extract effects and attributes"""
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
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
        try:
            # Check if strain already exists
            with get_db_cursor() as cur:
                cur.execute("SELECT id FROM strains WHERE canonical_name = %s", (strain_name,))
                existing = cur.fetchone()
                
                if existing:
                    logger.info(f"Strain '{strain_name}' already exists in database")
                    return str(existing['id'])
            
            # Classify the strain
            classification = self.classify_strain(strain_name, additional_context)
            
            # Store strain in database
            strain_id = upsert_strain(
                canonical_name=strain_name,
                strain_type=classification['strain_type'],
                effects=classification['effects']
            )
            
            # Store additional attributes
            with get_db_cursor() as cur:
                # Store medical uses
                for use in classification['medical_uses']:
                    cur.execute("""
                        INSERT INTO strain_effects (strain_id, effect, confidence)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (strain_id, f"medical_{use}", classification['confidence']))
                
                # Store flavors
                for flavor in classification['flavors']:
                    cur.execute("""
                        INSERT INTO strain_effects (strain_id, effect, confidence)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (strain_id, f"flavor_{flavor}", classification['confidence']))
            
            logger.info(f"Successfully classified and stored strain '{strain_name}' with ID {strain_id}")
            return strain_id
            
        except Exception as e:
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
        try:
            with get_db_cursor() as cur:
                # Get basic strain info
                cur.execute("""
                    SELECT canonical_name, strain_type 
                    FROM strains 
                    WHERE id = %s
                """, (strain_id,))
                
                strain_info = cur.fetchone()
                if not strain_info:
                    return {}
                
                # Get all effects
                cur.execute("""
                    SELECT effect, confidence 
                    FROM strain_effects 
                    WHERE strain_id = %s
                    ORDER BY confidence DESC
                """, (strain_id,))
                
                effects_data = cur.fetchall()
                
                # Categorize effects
                effects = []
                medical_uses = []
                flavors = []
                
                for effect_row in effects_data:
                    effect = effect_row['effect']
                    if effect.startswith('medical_'):
                        medical_uses.append(effect.replace('medical_', ''))
                    elif effect.startswith('flavor_'):
                        flavors.append(effect.replace('flavor_', ''))
                    else:
                        effects.append(effect)
                
                return {
                    'name': strain_info['canonical_name'],
                    'strain_type': strain_info['strain_type'],
                    'effects': effects,
                    'medical_uses': medical_uses,
                    'flavors': flavors
                }
                
        except Exception as e:
            logger.error(f"Error getting strain effects for {strain_id}: {e}")
            return {}
    
    def update_strain_classification(self, strain_name: str, force_reclassify: bool = False) -> str:
        """Update an existing strain's classification"""
        try:
            with get_db_cursor() as cur:
                cur.execute("SELECT id FROM strains WHERE canonical_name = %s", (strain_name,))
                existing = cur.fetchone()
                
                if not existing:
                    # Strain doesn't exist, classify and store
                    return self.classify_and_store_strain(strain_name)
                
                strain_id = str(existing['id'])
                
                if force_reclassify:
                    # Delete existing effects
                    cur.execute("DELETE FROM strain_effects WHERE strain_id = %s", (strain_id,))
                    
                    # Reclassify
                    classification = self.classify_strain(strain_name)
                    
                    # Update strain type
                    cur.execute("""
                        UPDATE strains 
                        SET strain_type = %s, updated_at = NOW()
                        WHERE id = %s
                    """, (classification['strain_type'], strain_id))
                    
                    # Store new effects
                    for effect in classification['effects']:
                        cur.execute("""
                            INSERT INTO strain_effects (strain_id, effect, confidence)
                            VALUES (%s, %s, %s)
                        """, (strain_id, effect, classification['confidence']))
                    
                    logger.info(f"Reclassified strain '{strain_name}'")
                
                return strain_id
                
        except Exception as e:
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