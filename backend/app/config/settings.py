from typing import List, Dict, Any
from app.llm.model_profiles import AVAILABLE_MODELS
from app.llm.prompt_builder.template_profiles import TEMPLATE_PROFILES

class Settings:
    @staticmethod
    def get_available_models() -> List[Dict[str, Any]]:
        # Dynamic fetch from ModelRegistry
        models = []
        for model in AVAILABLE_MODELS:
            models.append({
                "name": model["name"], 
                "description": model["description"], 
                "available": True
            })
        return models



    @staticmethod
    def get_available_templates() -> List[Dict[str, str]]:
        # Dynamic fetch from StyleRegistry
        templates = []
        for template in TEMPLATE_PROFILES:
            templates.append({
                "name": template["name"], 
                "description": template["description"]
            })
        return templates
