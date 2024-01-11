# utils.py
from functools import wraps

from .exceptions import Jinja2TemplateSyntaxError, Jinja2TemplateUndefinedError, PathError, FormatError
def normalize_body(body):
    return "<!DOCTYPE html>\n<html lang="'EN'"><body><div>" + body + "</div></body></html>"

def handle_exceptions(exception_handler_method):
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
