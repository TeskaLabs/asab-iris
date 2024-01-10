from abc import ABC, abstractmethod


class ExceptionManager(ABC):
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
        Asynchronously handles an exception.

        This abstract method should be implemented by the subclass to define specific
        strategies for handling exceptions. It can include logging, notifying, or recovering
        from exceptions based on the implementation.

        Args:
            exception (Exception): The exception that needs to be handled.
            notification_params (Optional[dict]): Additional parameters for notification purposes,
                such as user details, context of the exception, etc. Defaults to None.

        Returns:
            None: The method is meant for handling exceptions and does not return any value.

        Raises:
            NotImplementedError: If this method is not implemented in the subclass.
        """

        pass
