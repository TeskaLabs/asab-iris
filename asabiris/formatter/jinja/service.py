import logging
import asab
import re
import configparser
import collections
import jinja2
import json
import os

from ...exceptions import PathError
from ...formater_abc import FormatterABC

L = logging.getLogger(__name__)


class CaseInsensitiveDict(dict):
    """
    A dictionary subclass that provides case-insensitive access to its keys.
    """
    def __setitem__(self, key, value):
        super().__setitem__(key.upper(), value)

    def __getitem__(self, key):
        return super().__getitem__(key.upper())

    def get(self, key, default=None):
        return super().get(key.upper(), default)

    def setdefault(self, key, default=None):
        return super().setdefault(key.upper(), default)

    def update(self, other=None, **kwargs):
        if other is not None:
            for key, value in other.items():
                self[key] = value
        for key, value in kwargs.items():
            self[key] = value

    def __contains__(self, key):
        return super().__contains__(key.upper())



class JinjaFormatterService(asab.Service, FormatterABC):
    """
    JinjaFormatterService is responsible for formatting templates using Jinja2.
    It loads variables from the configuration and optionally from a JSON file.
    """

    def __init__(self, app, service_name="JinjaService"):
        super().__init__(app, service_name)
        self.Variables = CaseInsensitiveDict()

        # Load variables from the configuration section named 'variables'
        try:
            config_vars = {option.upper(): asab.Config.get('variables', option) for option in asab.Config.options('variables')}
            self.Variables.update(config_vars)
        except configparser.NoSectionError:
            self.Variables = CaseInsensitiveDict()  # No variables section in the config, continue with an empty Variables dictionary

        # Load variables from JSON file if specified in the configuration
        json_path = asab.Config.get('jinja', 'variables', fallback=None)
        if json_path and os.path.exists(json_path):
            with open(json_path, 'r') as json_file:
                json_data = {k.upper(): v for k, v in json.load(json_file).items()}
                self.Variables.update(json_data)  # This will overwrite any conflicting keys from the config
                print(self.Variables)
        self.Variables = CaseInsensitiveDict(self.Variables)

        print(self.Variables)
    async def format(self, template_path, template_params):
        # Normalize template_params keys to uppercase for internal handling
        template_params = CaseInsensitiveDict({k.upper(): v for k, v in template_params.items()})

        # Combine the provided template_params with the loaded Variables
        # Ensure that the ChainMap uses CaseInsensitiveDict to maintain case insensitivity
        jinja_variables = collections.ChainMap(template_params, self.Variables)

        # Read the template from the specified template_path
        template_io = await self.App.LibraryService.read(template_path)
        if template_io is None:
            raise PathError(use_case='slack', invalid_path=template_path)

        # Create a Jinja2 template from the read content
        template_content = template_io.read().decode('utf-8')
        template = jinja2.Template(template_content)

        # Convert keys with dot notation into nested dictionaries
        # Ensure that the nested dictionary is also case-insensitive
        nested_template_params = create_nested_dict_from_dots_in_keys(jinja_variables)

        # Prepare the parameters for rendering by matching the case of the template placeholders
        # We need to extract the placeholders from the template content
        placeholders = set(re.findall(r'\{\{\s*(\w+)\s*\}\}', template_content))
        rendering_params = {
            placeholder: nested_template_params.get(placeholder.upper())
            for placeholder in placeholders
        }

        # Render the template with the parameters that match the placeholders' case
        rendered_template = template.render(rendering_params)
        return rendered_template

def create_nested_dict_from_dots_in_keys(data):
    """
    This function creates a nested dictionary from a dictionary with keys containing dots.
    It uses a stack to keep track of dictionaries that need to be processed, avoiding recursion.
    """

    def insert_nested_dict(keys, value, nested_dict):
        for key in keys[:-1]:
            key = key.upper()  # Convert to uppercase for case-insensitivity
            nested_dict = nested_dict.setdefault(key, CaseInsensitiveDict())
        nested_dict[keys[-1].upper()] = value  # Convert to uppercase for case-insensitivity

    nested_dict = CaseInsensitiveDict()
    stack = [(list(data.items()), nested_dict)]

    while stack:
        current_data, current_dict = stack.pop()
        for key, value in current_data:
            keys = key.split('.')
            keys = [k.upper() for k in keys]  # Convert all parts to uppercase
            if isinstance(value, dict):
                new_dict = CaseInsensitiveDict()
                stack.append((list(value.items()), new_dict))
                insert_nested_dict(keys, new_dict, current_dict)
            else:
                insert_nested_dict(keys, value, current_dict)

    return nested_dict
