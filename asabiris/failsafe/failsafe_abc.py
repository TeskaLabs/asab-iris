from abc import ABC, abstractmethod


class FailsafeManager(ABC):
    @abstractmethod
    async def send_error_notification(self, error, sending_info):
        pass
