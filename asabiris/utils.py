import re
import logging

#

L = logging.getLogger(__name__)


#


def find_subject_in_html(body):
	regex = r"(<title>(.*)</title>)"
	match = re.search(regex, body)
	if match is None:
		return body, None
	subject_line, subject = match.groups()
	body = body.replace(subject_line, "")
	return body, subject


def find_subject_in_md(body):
	if not body.startswith("SUBJECT:"):
		return body, None
	subject = body.split("\n")[0].replace("SUBJECT:", "").lstrip()
	body = "\n".join(body.split("\n")[1:])
	return body, subject


def normalize_body(body):
	return "<!DOCTYPE html>\n<html lang="'EN'"><body><div>" + body + "</div></body></html>"


def create_nested_dict_from_dots_in_keys(data):
	"""
	Create a nested dictionary from a dictionary with keys containing dots.

	This function takes an input dictionary `data` that may contain keys with dots, indicating nested levels of dictionaries.
	It splits the keys containing dots and constructs a nested dictionary structure accordingly.

	:param data: The input dictionary that may contain keys with dots in them.
	:return: A nested dictionary where keys containing dots have been split into sub-dictionaries.

	Example:
	input: {'alert.event.id': 1, 'alert2': {'event': {'id': 2}}}
	output: {'alert': {'event': {'id': 1}}, 'alert2': {'event': {'id': 2}}}
	"""
	nested_dict = {}  # Initialize the nested dictionary
	stack = [(nested_dict, data)]  # Use a stack to keep track of dictionaries and their corresponding data
	keys_to_process = list(data.keys())  # Store the keys to process separately

	while stack:
		current_dict, current_data = stack.pop()

		for key in keys_to_process:
			value = current_data[key]

			parts = key.split('.')  # Split the key by dot ('.') delimiter
			nested = current_dict

			# Traverse the nested dictionary structure and create nested dictionaries as needed
			for part in parts[:-1]:
				if part not in nested:
					nested[part] = {}
				nested = nested[part]

			nested[parts[-1]] = value  # Assign the value to the last part of the key in the nested dictionary

			if isinstance(value, dict):
				stack.append(
					(nested[parts[-1]], value))  # Add nested dictionaries to the stack for further processing

		keys_to_process.clear()  # Clear the processed keys

	return nested_dict
