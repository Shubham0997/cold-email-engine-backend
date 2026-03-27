import os
import google.generativeai as genai
import json
import logging

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-3.1-pro-preview')
        else:
            self.model = None
            logger.warning("GEMINI_API_KEY not found in environment")

    def research_email(self, prompt: str):
        if not self.model:
            return {"error": "AI Service not configured (Missing API Key)"}

        system_prompt = """
        You are an expert cold email researcher and copywriter.
        Based on the user's prompt, research the topic and generate a compelling email.
        Return ONLY a JSON object with 'subject' and 'body' keys.
        Do not include any other text or markdown formatting.
        The 'body' should be professional and include placeholders like {{email}} if appropriate.
        """

        try:
            response = self.model.generate_content(
                f"{system_prompt}\n\nUser Prompt: {prompt}",
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json"
                )
            )
            
            # Clean up response text if it has markdown code blocks
            res_text = response.text.strip()
            if res_text.startswith("```json"):
                res_text = res_text[7:-3].strip()
            elif res_text.startswith("```"):
                res_text = res_text[3:-3].strip()
                
            return json.loads(res_text)
        except Exception as e:
            logger.error(f"AI Research failed: {e}")
            return {"error": str(e)}

    def generate_leads(self, prompt: str):
        if not self.model:
            return {"error": "AI Service not configured (Missing API Key)"}

        system_prompt = """
        You are an expert lead generator.
        Based on the user's prompt, find or suggest a list of 5-10 potential target email addresses or professional contact points.
        Return ONLY a JSON object with a 'leads' key containing a list of strings (emails).
        Do not include any other text or markdown formatting.
        If you cannot find real ones, suggest highly plausible professional emails based on the target audience.
        """

        try:
            response = self.model.generate_content(
                f"{system_prompt}\n\nUser Prompt: {prompt}",
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json"
                )
            )
            
            res_text = response.text.strip()
            if res_text.startswith("```json"):
                res_text = res_text[7:-3].strip()
            elif res_text.startswith("```"):
                res_text = res_text[3:-3].strip()
                
            return json.loads(res_text)
        except Exception as e:
            logger.error(f"Lead Generation failed: {e}")
            return {"error": str(e)}

ai_service = AIService()
