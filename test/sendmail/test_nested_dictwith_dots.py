import unittest
import logging
import asabiris.utils


L = logging.getLogger("__name__")


class TestNestedDictWithDos(unittest.TestCase):

	def tearDown(self):
		root_logger = logging.getLogger()
		root_logger.handlers = []

	def test_empty_dict(self):
		data = {}
		result = asabiris.utils.create_nested_dict_from_dots_in_keys(data)
		expected = {}
		self.assertDictEqual(result, expected)


	def test_nested_dict_01(self):
		data = {'alert': {'event.other.id': '1234'}}
		result = asabiris.utils.create_nested_dict_from_dots_in_keys(data)
		expected = {'alert': {'event.other.id': '1234'}}
		self.assertDictEqual(result, expected)


	def test_nested_dict_02(self):
		data = {'alert.event.id': 1, 'alert2': {'event': {'id': 2}}}
		result = asabiris.utils.create_nested_dict_from_dots_in_keys(data)
		expected = {'alert': {'event': {'id': 1}}, 'alert2': {'event': {'id': 2}}}
		self.assertDictEqual(result, expected)


	def test_nested_dict_03(self):
		data = {
			"name": "Alice",
			"age": 25,
			"address.city": "London",
			"address.country": "UK",
			"address.postcode": "SW1A 1AA",
			"education.primary.school": "Greenwich Primary School",
			"education.secondary.school": "Greenwich Secondary School"
		}
		result = asabiris.utils.create_nested_dict_from_dots_in_keys(data)
		expected = {
			"name": "Alice",
			"age": 25,
			"address": {
				"city": "London",
				"country": "UK",
				"postcode": "SW1A 1AA"
			},
			"education": {
				"primary": {
					"school": "Greenwich Primary School"
				},
				"secondary": {
					"school": "Greenwich Secondary School"
				}
			}
		}
		self.assertDictEqual(result, expected)
