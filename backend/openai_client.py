
import os
import openai
import logging

logger = logging.getLogger("openai-client")

class OpenAIClient:
    def __init__(self):
        self.api_key = os.environ.get('OPENAI_API_KEY')
        self.model = os.environ.get('OPENAI_MODEL', 'gpt-4')
        
        if not self.api_key:
            raise ValueError("OpenAI API key not found in environment variables")
        
        openai.api_key = self.api_key

    def get_completion(self, prompt: str, max_tokens: int = 2000) -> str:
        """Get completion from OpenAI"""
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful software development assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.1
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error getting OpenAI completion: {str(e)}")
            raise
