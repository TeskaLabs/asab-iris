"""
Helpers for applying ZooKeeper-backed configuration on top of the static ASAB config.

The intended flow is:

1. Load the regular static configuration from files and defaults.
2. Resolve a ZooKeeper node path from ``[config_zookeeper]``.
3. Read a single JSON document from that node.
4. Overlay any values found there into ``asab.Config``.

This keeps the rest of the application unchanged because services can continue to
read from ``asab.Config`` without knowing whether a value originally came from a
file or from ZooKeeper.
"""

import configparser
import json
import logging
import urllib.parse

import asab
import kazoo.exceptions

L = logging.getLogger(__name__)


def _stringify_config_value(value):
	"""
	Convert a JSON-derived value into the string representation expected by ``asab.Config``.

	ASAB configuration values are stored as strings, even when callers later read them
	back via helpers such as ``getboolean()`` or ``getint()``. This helper normalizes the
	values we read from ZooKeeper so they can be safely written into the in-memory config.

	Boolean values are converted to lowercase ``true`` / ``false`` strings because that
	format is accepted by ``ConfigParser.getboolean()``. Nested objects and lists are
	serialized back to JSON so they remain readable and deterministic. Everything else is
	converted with ``str()``.
	"""
	if isinstance(value, bool):
		return "true" if value else "false"
	if isinstance(value, (dict, list)):
		return json.dumps(value)
	return str(value)


def resolve_config_zookeeper_path(config, section_name="config_zookeeper"):
	"""
	Resolve the ZooKeeper node that stores config overrides.

	The preferred configuration is an explicit ``path`` in the selected section:

	``[config_zookeeper]``
	``path=/lmio/iris/config``

	For convenience, a ``zk://`` style ``url`` is also accepted and only its path
	component is used. This lets callers stay consistent with other ZooKeeper-related
	settings already present in the codebase.

	Returns the resolved ZooKeeper path as a string, or ``None`` when neither ``path``
	nor ``url`` is configured.
	"""
	path = config.get(section_name, "path", fallback="").strip()
	if path:
		return path

	url = config.get(section_name, "url", fallback="").strip()
	if not url:
		return None

	url_parts = urllib.parse.urlparse(url)
	return url_parts.path or None


def load_config_overrides(zk_client, path):
	"""
	Load the JSON config override document from ZooKeeper.

	The expected payload is a single JSON object shaped like ASAB config sections, for
	example::

		{
		  "smtp": {"host": "smtp.example.com", "port": "587"},
		  "slack": {"channel": "alerts"}
		}

	If the client is missing, the path is empty, the node does not exist, the node is
	empty, or ZooKeeper raises an operational read error, the function returns an empty
	mapping so the caller can transparently keep using the static configuration. Invalid
	JSON or a non-object payload is still treated as an error and raised to the caller so
	bootstrap code can log the problem clearly.
	"""
	if zk_client is None or not path:
		return {}

	try:
		data, _ = zk_client.get(path)
	except kazoo.exceptions.NoNodeError:
		L.info("ZooKeeper configuration path '%s' not found. Using static configuration.", path)
		return {}
	except kazoo.exceptions.KazooException as e:
		L.warning(
			"Failed to read ZooKeeper configuration path '%s': %s: %s. Using static configuration.",
			path,
			e.__class__.__name__,
			e,
		)
		return {}

	if data is None or data == b"":
		L.info("ZooKeeper configuration path '%s' is empty. Using static configuration.", path)
		return {}

	if isinstance(data, bytes):
		payload_raw = data.decode("utf-8")
	else:
		payload_raw = str(data)

	if payload_raw.strip() == "":
		L.info("ZooKeeper configuration path '%s' is empty. Using static configuration.", path)
		return {}

	payload = json.loads(payload_raw)
	if not isinstance(payload, dict):
		raise ValueError("ZooKeeper configuration payload must be a JSON object.")

	return payload


def apply_config_overrides(config, overrides):
	"""
	Merge ZooKeeper-provided values into an existing ``ConfigParser`` instance.

	The merge is intentionally shallow and section-oriented:

	- existing sections are updated in place
	- missing sections are created
	- missing static keys are preserved
	- keys explicitly provided by ZooKeeper win over static values
	- ``null`` / ``None`` values are ignored rather than deleting config entries

	This behavior keeps the overlay lean and predictable. The static configuration remains
	the baseline, while ZooKeeper only overrides the keys it actually provides.
	"""
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
	"""
	Apply ZooKeeper config overrides during application bootstrap.

	This is the high-level entry point used by the app startup sequence. It checks whether
	ZooKeeper is available, whether the selected config section is present, resolves the
	override node path, reads the JSON payload, and merges it into ``asab.Config``.

	The function is deliberately fail-soft for operational issues:

	- if ZooKeeper is not configured, it does nothing
	- if the override section is absent, it does nothing
	- if the path is missing, the node is absent, the node is empty, or ZooKeeper read fails, static config stays in effect
	- if parsing or validation fails, the problem is logged and static config stays in effect

	Returns ``True`` only when at least one override document was successfully applied.
	"""
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
