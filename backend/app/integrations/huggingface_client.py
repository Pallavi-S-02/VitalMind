import os
import requests
import logging

logger = logging.getLogger(__name__)

class HuggingFaceClient:
    """Direct client for HuggingFace Inference API"""
    
    def __init__(self):
        self.api_key = os.environ.get('HUGGINGFACE_API_KEY')
        self.api_url = "https://api-inference.huggingface.co/models/"
        self.headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        
    def _query(self, model_id, payload):
        if not self.api_key:
            return {"error": "HuggingFace API key not configured"}
            
        try:
            response = requests.post(
                f"{self.api_url}{model_id}", 
                headers=self.headers, 
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"HuggingFace API request failed: {str(e)}")
            return {"error": str(e)}

    def analyze_medical_image(self, image_data):
        """
        Analyze medical image (e.g., X-ray) using a vision model
        image_data should be base64 encoded or raw bytes
        """
        # Example using a medical image classification model
        # Note: In a real app, you'd use a specific medical vision model
        model_id = "google/vit-base-patch16-224" 
        
        payload = {"inputs": image_data}
        return self._query(model_id, payload)
        
    def extract_entities_from_text(self, text):
        """
        Extract medical entities (symptoms, drugs, etc.) from text
        """
        # Example using a medical NER model
        model_id = "d4data/biomedical-ner-all"
        
        payload = {"inputs": text}
        return self._query(model_id, payload)

# Singleton instance
hf_client = HuggingFaceClient()
