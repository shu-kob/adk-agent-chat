"""
Model Availability & Pre-flight Check Module
"""

import logging
from typing import List, Tuple, Dict, Any
from google.genai import types

logger = logging.getLogger("eval_precheck")

def validate_model_availability(client: Any, models: List[str]) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Sends a minimal pre-flight request to each model to verify accessibility.
    Returns (valid_models, skipped_models).
    """
    valid_models: List[str] = []
    skipped_models: List[Dict[str, str]] = []

    config = types.GenerateContentConfig(
        temperature=0.0,
        max_output_tokens=10
    )

    for model_id in models:
        try:
            resp = client.models.generate_content(
                model=model_id,
                contents="ping",
                config=config
            )
            if resp:
                valid_models.append(model_id)
        except Exception as e:
            error_str = str(e)
            logger.warning(f"Precheck failed for model '{model_id}': {error_str}. Skipping from evaluation.")
            skipped_models.append({
                "model_id": model_id,
                "error": error_str
            })

    return valid_models, skipped_models
