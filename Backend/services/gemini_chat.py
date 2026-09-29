import os
import google.generativeai as genai
from typing import Dict, Any, List

class GeminiChat:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def ask(self, message: str, context: Dict[str, Any]) -> str:
        prompt = f"""
        You are BudgetBuddy, a friendly and helpful financial AI assistant.
        The user has asked: "{message}"
        
        Here is the user's current financial context:
        Total Budget: {context.get('total_budget')}
        Total Spent: {context.get('total_spent')}
        Remaining: {context.get('remaining')}
        Top Categories: {context.get('top_categories')}
        Recent Expenses: {context.get('recent_expenses')}
        
        Provide a concise, helpful, and encouraging response (max 3-4 sentences). Do not use complex formatting.
        """
        response = self.model.generate_content(prompt)
        return response.text.strip()

    def generate_monthly_report(self, expenses: List[Any], month: int, year: int) -> str:
        if not expenses:
            return f"No expenses found for {month}/{year}. Nothing to report yet!"
            
        expense_lines = [f"- {e.expense_date}: {e.category} (₹{e.amount}) - {e.note}" for e in expenses]
        expense_text = "\n".join(expense_lines)
        
        prompt = f"""
        You are a financial advisor analyzing expenses for {month}/{year}.
        Generate a concise, insightful monthly report.
        Highlight the top spending areas, suggest 2-3 specific ways to save, and give an encouraging conclusion.
        Format the response in Markdown with headings.
        
        Expenses:
        {expense_text}
        """
        response = self.model.generate_content(prompt)
        return response.text.strip()
