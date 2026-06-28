from unicodedata import category

from groq import Groq
import os
from dotenv import load_dotenv
from pathlib import Path
import json

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class AICategorizer:

    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY")
        print(self.groq_key)

        self.client = Groq(api_key=self.groq_key)
        self.model = "llama-3.1-8b-instant"

    def categorize_expense(self, description: str) -> dict:

        prompt = f"""
        You are an expense classification system.
        Main Category:{category}
        Expense Note:{description}

        Determine the most specific subcategory.

        Rules:
        1. Use merchant name if available.
        2. Use app/service name if available.
        3. Use brand name if available.
        4. Use person's relation if money was given to someone.
        5. Maximum 3 words.
        6. Never return the main category.
        7. Return ONLY the subcategory.
        Examples:
        Food + "Had pizza from Domino's"
        Domino's

        Subscriptions + "Bought Hotstar Premium"
        Hotstar

        Transport + "Uber ride"
        Uber

        Family + "Given money to dad"
        Dad

        Gifts + "Bought a Superman toy"
        Superman Toy
        Expense:
        {description}
        Subcategory:
        """
        

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0
        )

        ai_response = response.choices[0].message.content.strip()
        print(ai_response)
        try:
            subcategory_dict = json.loads(ai_response)
            return subcategory_dict
        except json.JSONDecodeError:
            print("Failed to parse AI response as JSON. Returning default subcategory.")
            pass

        return {"subcategory": "Other"}