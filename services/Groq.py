# groq_client.py
import os
import json
import re
from groq import Groq
from services.PromptServices import system_prompt
from dotenv import load_dotenv


load_dotenv()



class GroqClient:
    def __init__(self, api_key: str = None, model: str = "llama-3.3-70b-versatile"):
        self.api_key = os.getenv("GROQ_API_KEY")
        # print("this si the api - - " , self.api_key)
        self.model = model
        self.client = Groq(api_key=self.api_key) if self.api_key else None
    
    def extract_customer_info(self, transcript: str) -> dict:
        print("this is the test 1")
        # print("this isthe transcript = " , transcript)
        print("this is the api key = " , os.getenv("GROQ_API_KEY"))
        if not self.client:
            return {"error": "Groq client not initialized"}
        

        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract customer information from this conversation:\n\n{transcript}"}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            # Extract JSON from response
            content = response.choices[0].message.content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)
            else:
                return {"error": "No JSON found in response"}
                
        except Exception as e:
            return {"error": f"Extraction failed: {str(e)}"}
        

        