from typing import List, Tuple
from fpdf import FPDF
from datetime import date
from models.expense_model import Expense
from services.export.provider_interface import BaseExportProvider

class PDFExportProvider(BaseExportProvider):
    def generate(self, expenses: List[Expense]) -> Tuple[bytes, str]:
        # 1. Initialize PDF
        pdf = FPDF(orientation='L', unit='mm', format='A4') # Landscape for tabular data
        pdf.add_page()
        
        # 2. Add Title
        pdf.set_font('Helvetica', 'B', 16)
        pdf.cell(0, 10, 'BudgetBuddy Expense Report', ln=True, align='C')
        
        # 3. Add Export Date & Summary
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 8, f'Generated on: {date.today().isoformat()}', ln=True, align='C')
        
        total_amount = sum(e.amount for e in expenses if e.amount is not None)
        pdf.cell(0, 8, f'Total Expenses: {len(expenses)} | Total Amount: ₹{total_amount:,.2f}', ln=True, align='C')
        pdf.ln(5)
        
        # 4. Table Header
        pdf.set_font('Helvetica', 'B', 10)
        # Define column widths
        # Total width in A4 Landscape is ~277mm inside margins
        col_widths = [30, 35, 35, 25, 35, 87, 30]
        headers = ["Date", "Category", "Subcategory", "Amount", "Pay Method", "Note", "Created At"]
        
        # Header background
        pdf.set_fill_color(31, 78, 120) # #1F4E78
        pdf.set_text_color(255, 255, 255)
        
        for w, h in zip(col_widths, headers):
            pdf.cell(w, 10, h, border=1, align='C', fill=True)
        pdf.ln()
        
        # 5. Table Rows
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Helvetica', '', 9)
        
        for exp in expenses:
            date_str = exp.expense_date.isoformat() if exp.expense_date else ""
            created_str = exp.created_at.strftime("%Y-%m-%d") if exp.created_at else ""
            amount_str = f"Rs {exp.amount:,.2f}" if exp.amount is not None else "0.00"
            note_str = exp.note or ""
            # Truncate note if too long
            if len(note_str) > 45:
                note_str = note_str[:42] + "..."
                
            row_data = [
                date_str,
                exp.category or "",
                exp.subcategory or "",
                amount_str,
                exp.payment_method or "",
                note_str,
                created_str
            ]
            
            for w, item in zip(col_widths, row_data):
                pdf.cell(w, 8, str(item), border=1)
            pdf.ln()
            
        # 6. Generate Bytes
        # FPDF .output(dest='S') returns a string (latin1) which we must encode to bytes.
        pdf_bytes = pdf.output(dest='S').encode('latin1')
        mime_type = "application/pdf"
        
        return pdf_bytes, mime_type
