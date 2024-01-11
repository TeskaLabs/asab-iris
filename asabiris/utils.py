# utils.py
from functools import wraps

from .exceptions import Jinja2TemplateSyntaxError, Jinja2TemplateUndefinedError, PathError, FormatError


def normalize_body(body):
    return "<!DOCTYPE html>\n<html lang="'EN'"><body><div>" + body + "</div></body></html>"


def handle_exceptions(exception_handler_method):
    """
    A decorator factory for exception handling in asynchronous functions.

    This factory returns a decorator that wraps an asynchronous function with a try-except block.
    In case of an exception, it delegates the handling to a specified exception handling method
    of the object (typically a class instance) to which the function belongs.

    The decorator catches several specific exceptions, such as Jinja2 template errors and general exceptions.
    Upon catching an exception, it invokes the exception handling method defined in the class,
    passing the exception and an empty dictionary as arguments.

    Args:
        exception_handler_method (str): The name of the method in the class that handles exceptions.
                                        This method should be an async method taking two parameters:
                                        the exception and a dictionary for additional context.

    Returns:
        Callable: A decorator that can be applied to async methods of a class.

    Example:
        class MyClass:
            async def exception_handler(self, exception, context):
                # Handle exception here

            @handle_exceptions('exception_handler')
            async def my_async_method(self, arg1, arg2):
                # Method implementation

    Note:
        The decorated function must be an asynchronous method of a class.
        The class should have the specified exception handling method.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)
            except (Jinja2TemplateSyntaxError, Jinja2TemplateUndefinedError, FormatError, PathError, Exception) as e:
                exception_handler = getattr(self, exception_handler_method)
                await exception_handler.handle_exception(e, {})
        return wrapper
    return decorator
