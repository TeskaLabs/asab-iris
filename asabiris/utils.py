import yaml

from .errors import ASABIrisError, ErrorCode


def normalize_body(body):
	return "<!DOCTYPE html>\n<html lang="'EN'"><body><div>" + body + "</div></body></html>"


async def read_yaml(library_service, path):
	async with library_service.open(path) as b:
		if b is None:
			raise ASABIrisError(
				ErrorCode.FAILED_READ_FROM_LIBRARY,
				error_dict={"path": path},
				tech_message="Failed to read Library declaration: file is not in the Library or couldn't be read due to technical reasons",
				error_i18n_key="Declaration '{{path}}' is not in the Library or couldn't be read."
			)
		return yaml.safe_load(b.read())
