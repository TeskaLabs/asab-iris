from abc import ABC, abstractmethod


class ExceptionHandlingStrategy(ABC):
    @abstractmethod
    async def handle_exception(self, exception, notification_params):
        pass
