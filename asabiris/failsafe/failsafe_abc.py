from abc import ABC, abstractmethod


class FailsafeHandler(ABC):
    @abstractmethod
    async def send_error_notification(self, error, sending_info):
        pass
