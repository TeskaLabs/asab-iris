import logging
import asab
import configparser
import collections
import jinja2
import json
import os

from ...exceptions import PathError
from ...formater_abc import FormatterABC
from ... import utils

L = logging.getLogger(__name__)


class CaseInsensitiveDict(dict):
    """
    A dictionary subclass that provides case-insensitive access to its keys.
    """
    def __getitem__(self, key):
        return super().__getitem__(key.upper())

    def get(self, key, default=None):
        return super().get(key.upper(), default)


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

        self.Variables = CaseInsensitiveDict(self.Variables)

    async def format(self, template_path, template_params):
        # Convert template_params to be case-insensitive
        template_params = CaseInsensitiveDict(template_params)

        # Combine the provided template_params with the loaded Variables
        jinja_variables = collections.ChainMap(template_params, self.Variables)
        # Read the template from the specified template_path
        template_io = await self.App.LibraryService.read(template_path)
        if template_io is None:
            raise PathError(f"Template '{template_path}' not found")

        # Create a Jinja2 template from the read content
        template = jinja2.Template(template_io.read().decode('utf-8'))

        # Convert keys with dot notation into nested dictionaries
        template_params = utils.create_nested_dict_from_dots_in_keys(jinja_variables)

        # Render the template with the combined variables
        return template.render(**template_params)
