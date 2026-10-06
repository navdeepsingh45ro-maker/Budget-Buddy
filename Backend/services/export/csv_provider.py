import csv
import io
from typing import List, Tuple
from models.expense_model import Expense
from services.export.provider_interface import BaseExportProvider
from services.export.provider_interface import safe_cell

class CSVExportProvider(BaseExportProvider):
    def generate(self, expenses: List[Expense]) -> Tuple[bytes, str]:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Expense Date",
            "Category",
            "Subcategory",
            "Amount",
            "Payment Method",
            "Note",
            "Created At"
        ])
        
        # Write rows
        for exp in expenses:
            date_str = exp.expense_date.isoformat() if exp.expense_date else ""
            created_str = exp.created_at.strftime("%Y-%m-%d %H:%M:%S") if exp.created_at else ""
            
            writer.writerow([
                date_str,
                safe_cell(exp.category),
                safe_cell(exp.subcategory),
                f"{exp.amount:.2f}" if exp.amount is not None else "0.00",
                safe_cell(exp.payment_method),
                safe_cell(exp.note),
                created_str
            ])
            
        csv_bytes = output.getvalue().encode('utf-8')
        mime_type = "text/csv"
        
        return csv_bytes, mime_type
