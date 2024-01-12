# utils.py
from functools import wraps
import inspect
from .exceptions import Jinja2TemplateSyntaxError, Jinja2TemplateUndefinedError, PathError, FormatError


def normalize_body(body):
    return "<!DOCTYPE html>\n<html lang="'EN'"><body><div>" + body + "</div></body></html>"
