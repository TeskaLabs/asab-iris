import configparser
import json
import logging
import urllib.parse

import asab


L = logging.getLogger(__name__)


def _stringify_config_value(value):
	if isinstance(value, bool):
		return "true" if value else "false"
	if isinstance(value, (dict, list)):
		return json.dumps(value)
	return str(value)


def resolve_config_zookeeper_path(config, section_name="config_zookeeper"):
	path = config.get(section_name, "path", fallback="").strip()
	if path:
		return path

	url = config.get(section_name, "url", fallback="").strip()
	if not url:
		return None

	url_parts = urllib.parse.urlparse(url)
	return url_parts.path or None


def load_config_overrides(zk_client, path):
	if zk_client is None or not path:
		return {}

	if not zk_client.exists(path):
		L.info("ZooKeeper configuration path '%s' not found. Using static configuration.", path)
		return {}

	data, _ = zk_client.get(path)
	if data is None:
		L.info("ZooKeeper configuration path '%s' is empty. Using static configuration.", path)
		return {}

	if isinstance(data, bytes):
		payload_raw = data.decode("utf-8")
	else:
		payload_raw = str(data)

	payload = json.loads(payload_raw)
	if not isinstance(payload, dict):
		raise ValueError("ZooKeeper configuration payload must be a JSON object.")

	return payload


def apply_config_overrides(config, overrides):
	if not isinstance(overrides, dict):
		raise ValueError("ZooKeeper configuration overrides must be a mapping.")

	for section_name, section_values in overrides.items():
		if not isinstance(section_name, str):
			raise ValueError("ZooKeeper configuration section names must be strings.")
		if not isinstance(section_values, dict):
			raise ValueError(
				"ZooKeeper configuration section '{}' must contain a JSON object.".format(section_name)
			)

		if not config.has_section(section_name):
			config.add_section(section_name)

		for option_name, option_value in section_values.items():
			if option_value is None:
				continue

			config.set(
				section_name,
				str(option_name),
				_stringify_config_value(option_value),
			)


def apply_zookeeper_config_overrides(app, section_name="config_zookeeper"):
	if app.ZooKeeperContainer is None:
		return False

	if not asab.Config.has_section(section_name):
		return False

	try:
		path = resolve_config_zookeeper_path(asab.Config, section_name=section_name)
		if not path:
			L.warning(
				"Section [%s] is present but neither 'path' nor 'url' is configured. Using static configuration.",
				section_name,
			)
			return False

		overrides = load_config_overrides(app.ZooKeeperContainer.ZooKeeper.Client, path)
		if len(overrides) == 0:
			return False

		apply_config_overrides(asab.Config, overrides)
		L.info("Applied ZooKeeper configuration overrides from '%s'.", path)
		return True

	except (configparser.Error, ValueError, json.JSONDecodeError) as e:
		L.warning(
			"Failed to apply ZooKeeper configuration overrides from [%s]: %s. Using static configuration.",
			section_name,
			e,
		)
		return False
