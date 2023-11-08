import logging

#

L = logging.getLogger(__name__)


#


def normalize_body(body):
	return "<!DOCTYPE html>\n<html lang="'EN'"><body><div>" + body + "</div></body></html>"


def create_nested_dict_from_dots_in_keys(data):
	"""
	This function creates a nested dictionary from a dictionary with keys containing dots.
	It uses a stack to keep track of dictionaries that need to be processed, avoiding recursion.

	:param data: The input dictionary that may contain keys with dots in them, indicating nested levels
	of dictionaries. For example:
	:return: a nested dictionary where keys containing dots (".") have been split into sub-dictionaries.
	"""

	# Helper function to insert a value into the nested dictionary at the location specified by the list of keys
	def insert_nested_dict(keys, value, nested_dict):
		for key in keys[:-1]:
			# Ensure that the dictionary at the current level has a key for the next level
			nested_dict = nested_dict.setdefault(key, {})
		# Insert the value at the final level
		nested_dict[keys[-1]] = value

	# Initialize the nested dictionary and the stack with the input data
	nested_dict = {}
	stack = [(list(data.items()), nested_dict)]

	# Process dictionaries on the stack
	while stack:
		current_data, current_dict = stack.pop()
		for key, value in current_data:
			if '.' in key:
				# Split the key into parts and create nested dictionaries for each part
				keys = key.split('.')
				if isinstance(value, dict):
					# If the value is a dictionary, add it to the stack to be processed later
					new_dict = {}
					stack.append((list(value.items()), new_dict))
					insert_nested_dict(keys, new_dict, current_dict)
				else:
					# If the value is not a dictionary, insert it directly into the nested dictionary
					insert_nested_dict(keys, value, current_dict)
			else:
				# If the key does not contain a dot, handle it as a normal key-value pair
				if isinstance(value, dict):
					# If the value is a dictionary, add it to the stack to be processed later
					new_dict = {}
					stack.append((list(value.items()), new_dict))
					current_dict[key] = new_dict
				else:
					# If the value is not a dictionary, insert it directly into the nested dictionary
					current_dict[key] = value
	return nested_dict
