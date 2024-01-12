from abc import ABC, abstractmethod


class ExceptionStrategy(ABC):
    """
    Abstract base class that provides a blueprint for implementing exception handling mechanisms.

    This class is designed to be subclassed by concrete classes that implement specific strategies
    for handling exceptions. The primary method, `handle_exception`, is an asynchronous abstract method
    that must be overridden in the subclass.

    Attributes:
        None

    Methods:
        handle_exception: An abstract asynchronous method to handle exceptions.
    """
    @abstractmethod
    async def handle_exception(self, exception, notification_params=None):
        """
        This abstract base class defines a blueprint for implementing exception handling mechanisms.

        It is intended to be subclassed by concrete classes that specify how to handle exceptions.
        The primary method, `handle_exception`, is an asynchronous abstract method that subclasses
        must implement, defining their specific exception handling strategies, such as logging,
        notifying, or recovering from exceptions.

        Methods:
            handle_exception: An abstract asynchronous method to be implemented by subclasses
            for handling exceptions.
        """

        pass
