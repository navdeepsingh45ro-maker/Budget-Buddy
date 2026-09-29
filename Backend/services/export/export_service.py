from typing import Tuple, Optional
from datetime import date
from sqlalchemy.orm import Session
from services.expense_query_service import ExpenseQueryService
from services.export.csv_provider import CSVExportProvider
from services.export.excel_provider import ExcelExportProvider
from services.export.pdf_provider import PDFExportProvider

class ExportService:
    @staticmethod
    def generate_export(
        db: Session,
        user_id: int,
        format_type: str,
        search: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        sort: Optional[str] = "newest"
    ) -> Tuple[bytes, str, str]:
        """
        Coordinates the export process.
        Returns: (file_bytes, mime_type, filename)
        """
        # 1. Fetch filtered dataset directly from ExpenseQueryService, skipping pagination
        query_result = ExpenseQueryService.query(
            db=db,
            user_id=user_id,
            search=search,
            category=category,
            start_date=start_date,
            end_date=end_date,
            min_amount=min_amount,
            max_amount=max_amount,
            sort=sort,
            skip_pagination=True
        )
        expenses = query_result["expenses"]

        if not expenses:
            raise ValueError("No data available to export for the given filters.")

        # 2. Select Provider
        if format_type == "csv":
            provider = CSVExportProvider()
            ext = "csv"
        elif format_type == "excel":
            provider = ExcelExportProvider()
            ext = "xlsx"
        elif format_type == "pdf":
            provider = PDFExportProvider()
            ext = "pdf"
        else:
            raise ValueError(f"Unsupported export format: {format_type}")

        # 3. Generate File
        file_bytes, mime_type = provider.generate(expenses)

        # 4. Generate Filename
        today_str = date.today().isoformat()
        filename = f"Expenses_{today_str}.{ext}"

        return file_bytes, mime_type, filename
