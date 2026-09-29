from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAdapter(ABC):
    """
    Common interface for all platform notification adapters.
    Every platform adapter (Android, iOS, Web, Email, SMS) must inherit from this.
    """

    @abstractmethod
    def send(self, notification_data: Dict[str, Any], device_token: str) -> bool:
        """
        Dispatches the notification payload to the specific platform service.
        Returns True if dispatched successfully to the provider, False otherwise.
        """
        pass

    @abstractmethod
    def update_status(self, notification_id: int, status: str) -> bool:
        """
        Updates the delivery status of a notification after provider callback/response.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Checks if this adapter is configured and ready to send notifications.
        e.g., verifying SDK initialization or API keys.
        """
        pass

    @abstractmethod
    def validate_device(self, device) -> bool:
        """
        Validates if the provided device record has the necessary tokens
        or configuration to receive a notification via this adapter.
        """
        pass
