import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.prompts import PromptTemplate
import logging

logger = logging.getLogger(__name__)

class LangChainClient:
    """Client for interacting with LangChain and Google Gemini models"""
    
    def __init__(self):
        self.api_key = os.environ.get('GOOGLE_API_KEY')
        self._llm = None
        
    @property
    def llm(self):
        if self._llm is None and self.api_key:
            try:
                self._llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash",
                    google_api_key=self.api_key,
                    temperature=0.7,
                    
                )
            except Exception as e:
                logger.error(f"Failed to initialize Gemini LLM: {str(e)}")
        return self._llm
        
    def generate_clinical_summary(self, patient_data, recent_reports):
        """Generate a clinical summary for a patient"""
        if not self.llm:
            return "AI summary generation is currently unavailable."
            
        prompt = (
            "You are an AI medical assistant. Please provide a concise clinical summary "
            "based on the following patient data and recent reports.\n\n"
            f"Patient Data:\n{patient_data}\n\nRecent Reports:\n{recent_reports}\n\nSummary:"
        )
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return "Error generating summary."
            
    def analyze_symptoms(self, symptoms_text):
        """Analyze symptoms and suggest possible causes or next steps"""
        if not self.llm:
            return "AI analysis is currently unavailable."
            
        prompt = (
            "You are an AI medical assistant. Analyze the following symptoms and provide potential "
            "causes and recommendations for next steps. "
            "IMPORTANT: Always include a disclaimer that this is not a medical diagnosis.\n\n"
            f"Symptoms:\n{symptoms_text}\n\nAnalysis and Recommendations:"
        )
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            logger.error(f"Error analyzing symptoms: {str(e)}")
            return "Error analyzing symptoms."

# Singleton instance
langchain_client = LangChainClient()
