import unittest
from unittest.mock import patch, MagicMock, mock_open
from asabiris.formatter.jinja.service import JinjaFormatterService


class TestJinjaFormatterService(unittest.TestCase):
    """
    Unit tests for the JinjaFormatterService class.
    """

    @patch('builtins.open', new_callable=mock_open, read_data='{"key": "value"}')
    @patch('pathlib.Path.is_file')
    @patch('asabiris.formatter.jinja.service.asab.Config.get')
    def test_successful_json_load(self, mock_config_get, mock_is_file, _):
        """
        Test loading variables from a valid JSON file.
        Ensures that variables are correctly loaded and updated.
        """
        mock_config_get.return_value = 'valid.json'
        mock_is_file.return_value = True
        mock_app = MagicMock()
        service = JinjaFormatterService(mock_app)
        service._load_variables_from_json()
        self.assertEqual(service.Variables, {"key": "value"})

    @patch('builtins.open', new_callable=mock_open, read_data='Not a JSON')
    @patch('pathlib.Path.is_file')
    @patch('asabiris.formatter.jinja.service.asab.Config.get')
    def test_invalid_json_format(self, mock_config_get, mock_is_file, _):
        """
        Test behavior when the JSON file is not properly formatted.
        Ensures that the method handles invalid JSON gracefully.
        """
        mock_config_get.return_value = 'invalid.json'
        mock_is_file.return_value = True
        mock_app = MagicMock()
        service = JinjaFormatterService(mock_app)
        service._load_variables_from_json()
        self.assertEqual(service.Variables, {})

    @patch('builtins.open', mock_open(), create=True)
    @patch('pathlib.Path.is_file')
    @patch('asabiris.formatter.jinja.service.asab.Config.get')
    def test_io_error_on_file_open(self, mock_config_get, mock_is_file):
        """
        Test the handling of IOError when opening the JSON file.
        Ensures that the method handles file opening errors correctly.
        """
        mock_config_get.return_value = 'error.json'
        mock_is_file.return_value = True
        mock_open.side_effect = IOError("Failed to open file")
        mock_app = MagicMock()
        service = JinjaFormatterService(mock_app)
        service._load_variables_from_json()
        self.assertEqual(service.Variables, {})

    @patch('builtins.open', new_callable=mock_open, read_data='{"key": "new_value"}')
    @patch('pathlib.Path.is_file')
    @patch('asabiris.formatter.jinja.service.asab.Config.get')
    def test_update_existing_variables(self, mock_config_get, mock_is_file, _):
        """
        Test updating existing variables with new values from the JSON file.
        Ensures that existing variables are correctly updated.
        """
        mock_config_get.return_value = 'update.json'
        mock_is_file.return_value = True
        mock_app = MagicMock()
        service = JinjaFormatterService(mock_app)
        service.Variables = {"key": "old_value"}
        service._load_variables_from_json()
        self.assertEqual(service.Variables, {"key": "new_value"})

    @patch('builtins.open', new_callable=mock_open, read_data='{"new_key": "value"}')
    @patch('pathlib.Path.is_file')
    @patch('asabiris.formatter.jinja.service.asab.Config.get')
    def test_add_new_variables(self, mock_config_get, mock_is_file, _):
        """
        Test adding new variables from the JSON file to existing ones.
        Ensures that new variables are correctly added.
        """
        mock_config_get.return_value = 'add.json'
        mock_is_file.return_value = True
        mock_app = MagicMock()
        service = JinjaFormatterService(mock_app)
        service.Variables = {"existing_key": "existing_value"}
        service._load_variables_from_json()
        self.assertEqual(service.Variables, {"existing_key": "existing_value", "new_key": "value"})

    @patch('builtins.open', new_callable=mock_open, read_data='{}')
    @patch('pathlib.Path.is_file')
    @patch('asabiris.formatter.jinja.service.asab.Config.get')
    def test_empty_json_file(self, mock_config_get, mock_is_file, _):
        """
        Test behavior when the JSON file is empty.
        Ensures that the method handles empty JSON files correctly.
        """
        mock_config_get.return_value = 'empty.json'
        mock_is_file.return_value = True
        mock_app = MagicMock()
        service = JinjaFormatterService(mock_app)
        service._load_variables_from_json()
        self.assertEqual(service.Variables, {})


    @patch('builtins.open', new_callable=mock_open, read_data='{"complex": {"nested": {"key": ["value1", {"subkey": "subvalue"}]}}}')
    @patch('pathlib.Path.is_file')
    @patch('asabiris.formatter.jinja.service.asab.Config.get')
    def test_complex_nested_json_structure(self, mock_config_get, mock_is_file, _):
        """
        Test loading variables from a JSON file with a complex nested structure.
        This test is designed to challenge the method's ability to handle complex JSON structures.
        """
        mock_config_get.return_value = 'complex.json'
        mock_is_file.return_value = True
        mock_app = MagicMock()
        service = JinjaFormatterService(mock_app)
        service._load_variables_from_json()
        # Check if the method can handle and correctly parse the complex structure
        expected_structure = {"complex": {"nested": {"key": ["value1", {"subkey": "subvalue"}]}}}
        self.assertEqual(service.Variables, expected_structure)




if __name__ == '__main__':
    unittest.main()
