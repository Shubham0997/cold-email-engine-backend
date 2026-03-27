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

    def research_email(self, prompt: str, is_campaign: bool = False):
        if not self.model:
            return {"error": "AI Service not configured (Missing API Key)"}

        placeholder_guidance = ""
        if is_campaign:
            placeholder_guidance = """
            IMPORTANT: This is for a bulk email campaign. Do NOT use individual placeholders like {{name}}, {{company}}, or {{recent_topic}}.
            Instead, write a message that is professional and personalized to the 'group' or 'niche' the user described, but does not require individual data for each recipient.
            Ensure the message is 'ready to send' for a group of leads.
            You may still use {{email}} if useful, as the system handles it.
            """
        else:
            placeholder_guidance = "You may use placeholders like {{name}} or {{company}} if appropriate for a single outreach."

        system_prompt = f"""
        You are a world-class cold email researcher and copywriter.
        Based on the user's prompt, generate a professional, extensive, and theme-specific email subject and body.
        
        {placeholder_guidance}
        
        BRAND VOICE ANALYSIS:
        - Analyze the brand name, product, or URL mentioned in the prompt.
        - Adopt the specific voice, personality, and specialized terminology of that brand.
        - If it's a craft niche (like specialty coffee), use appropriate industry terms (e.g., 'extraction', 'profile', 'dialing in').
        - The tone should be helpful, knowledgeable, and inviting.
        
        STRUCTURE:
        - SUBJECT: Catchy, curiosity-driven, or value-first.
        - BODY: 
          1. Connect with the recipient's niche.
          2. Introduce the specific value proposition of the product or offering.
          3. Clear Call-To-Action (CTA).
          
        Return ONLY a JSON object with 'subject' and 'body' keys.
        Do not include any other text or markdown formatting.
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
