from abc import ABC, abstractmethod
from typing import List, Tuple
from models.expense_model import Expense

class BaseExportProvider(ABC):
    """
    Abstract base class for all export providers.
    """
    
    @abstractmethod
    def generate(self, expenses: List[Expense]) -> Tuple[bytes, str]:
        """
        Generate the export file.
        
        Args:
            expenses: List of filtered Expense objects.
            
        Returns:
            A tuple of (file_content_in_bytes, mime_type)
        """
        pass
