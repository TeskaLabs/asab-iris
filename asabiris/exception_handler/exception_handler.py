from abc import ABC, abstractmethod

class ExceptionHandlingStrategy(ABC):
    @abstractmethod
    async def handle_exception(self, exception, context_strategy):
        pass
