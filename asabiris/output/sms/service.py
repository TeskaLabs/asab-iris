import logging
import hashlib
import datetime
import secrets
import xml.etree.ElementTree as ET

import asab
import aiohttp
import pytz

from ...output_abc import OutputABC
from ...errors import ASABIrisError, ErrorCode

L = logging.getLogger(__name__)

asab.Config.add_defaults({
	'sms': {
		"login": "",
		"password": "",
		"timestamp_format": "%Y%m%dT%H%M%S",
		"api_url": "https://api.smsbrana.cz/smsconnect/http.php",
		# Optional keys (added to avoid NoOptionError and allow sane fallbacks)
		"phone": "",
		"timezone": "Europe/Prague",
	}
})


class SMSOutputService(asab.Service, OutputABC):
	ERROR_CODE_MAPPING = {
		'-1': "Duplicate user_id - a similarly marked SMS has already been sent in the past.",
		'1': "Unknown error.",
		'2': "Invalid login.",
		'3': "Invalid hash or password (depending on the login security variant).",
		'4': "Invalid time, greater time deviation between servers than the maximum accepted in the SMS Connect service settings.",
		'5': "Unauthorized IP, see SMS Connect service settings.",
		'6': "Invalid action name.",
		'7': "This sul has already been used once for the given day.",
		'8': "No connection to the database.",
		'9': "Insufficient credit.",
		'10': "Invalid recipient phone number.",
		'11': "Empty message text.",
		'12': "SMS is longer than the allowed 459 characters.",
	}

	def __init__(self, app, service_name="SMSOutputService"):
		super().__init__(app, service_name)

		self.Login = asab.Config.get("sms", "login", fallback=None)

		self.Password = asab.Config.get("sms", "password", fallback=None)
		self.Password = self.Password.strip() if self.Password else None

		self.TimestampFormat = asab.Config.get(
			"sms", "timestamp_format", fallback="%Y%m%dT%H%M%S"
		)

		self.ApiUrl = asab.Config.get(
			"sms", "api_url", fallback="https://api.smsbrana.cz/smsconnect/http.php"
		)

		tz_name = asab.Config.get("sms", "timezone", fallback="Europe/Prague")
		try:
			self.TimeZone = pytz.timezone(tz_name)
		except Exception:
			L.warning("Invalid timezone '{}', falling back to Europe/Prague.".format(tz_name))
			self.TimeZone = pytz.timezone("Europe/Prague")

		raw_phone = asab.Config.get("sms", "phone", fallback=None)
		self.GlobalPhone = raw_phone.strip() if raw_phone else None

		# Get tenant configuration service
		self.ConfigService = app.get_service("TenantConfigExtractionService")

	def generate_auth_params(self, password):
		"""
		Generates authentication parameters required by the SMS API.
		Uses the provided password (tenant or global).
		"""
		time_now = datetime.datetime.now(self.TimeZone).strftime(self.TimestampFormat)
		sul = secrets.token_urlsafe(16)
		auth_string = "{}{}{}".format(password, time_now, sul)
		auth = hashlib.md5(auth_string.encode('utf-8')).hexdigest()
		return time_now, sul, auth

	def split_message(self, message, first_segment_length=160, subsequent_segment_length=153):
		parts = []
		while message:
			part = message[:first_segment_length] if len(parts) == 0 else message[:subsequent_segment_length]
			parts.append(part)
			message = message[len(part):]
		return parts

	async def send(self, sms_data, tenant=None):
		"""
		Sends an SMS using either tenant-specific or global SMS settings,
		and falls back to a default phone if none is provided per-call.
		"""
		# 0) Validate message_body presence early
		message_body = sms_data.get("message_body")
		if not message_body:
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="Empty message body.",
				error_i18n_key="Invalid input: {{error_message}}.",
				error_dict={"error_message": "Empty message body."}
			)

		# 1) Start with global credentials and optional global default phone
		login, password, api_url = self.Login, self.Password, self.ApiUrl

		# Prefer not to trust blanks/whitespace
		def _clean(s):
			return str(s).strip() if s is not None else None

		body_phone = _clean(sms_data.get("phone"))
		phone_tenant = None

		# 2) If tenant is specified, attempt to load tenant creds and phone
		if tenant:
			login_tenant = None
			password_tenant = None
			api_url_tenant = None

			try:
				conf = self.ConfigService.get_sms_config(tenant)
			except Exception as err:
				L.warning("Failed to load tenant '{}' SMS config: {}".format(tenant, err))
				conf = None

			# Accept tuple/list (3 or 4 items) or dict
			if conf:
				if isinstance(conf, (list, tuple)):
					if len(conf) >= 3:
						login_tenant, password_tenant, api_url_tenant = conf[0], conf[1], conf[2]
						if len(conf) >= 4:
							phone_tenant = _clean(conf[3])
					else:
						L.warning("Tenant '{}' SMS config tuple too short: {}".format(tenant, conf))
				elif isinstance(conf, dict):
					login_tenant = conf.get("login")
					password_tenant = conf.get("password")
					api_url_tenant = conf.get("api_url")
					phone_tenant = _clean(conf.get("phone"))
				else:
					L.warning("Tenant '{}' SMS config in unexpected format.".format(tenant))

			# Override creds if all three tenant values are present
			if login_tenant and password_tenant and api_url_tenant:
				login, password, api_url = login_tenant, password_tenant, api_url_tenant
			else:
				L.warning("Tenant '{}' SMS config incomplete—using global credentials.".format(tenant))

		# Resolve phone with precedence: tenant > API body > global config
		global_phone = _clean(self.GlobalPhone)
		phone = next((p for p in (phone_tenant, body_phone, global_phone) if p), None)

		# 3) Validate that we have a phone number from at least one source
		if not phone:
			L.warning("No phone number provided (tenant/api/config).")
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="No phone number provided (tenant/api/config).",
				error_i18n_key="Invalid input: {{error_message}}.",
				error_dict={"error_message": "Phone number is required (tenant, request body, or config)."}
			)

		# 4) Validate that we have credentials and URL
		if not (login and password and api_url):
			L.error("Missing SMS configuration (login, password, or API URL).")
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="Missing SMS configuration (login, password, or API URL).",
				error_i18n_key="Invalid input: {{error_message}}.",
				error_dict={"error_message": "Missing SMS configuration (login, password, or API URL)."}
			)

		# 5) Normalize message_body into a list of strings
		if isinstance(message_body, str):
			message_list = [message_body]
		else:
			message_list = list(message_body)

		# 6) Reuse one session with a reasonable timeout
		timeout = aiohttp.ClientTimeout(total=15)
		async with aiohttp.ClientSession(timeout=timeout) as session:
			for message in message_list:
				# Clean message
				message = str(message).replace("\n", " ").strip()
				if not message:
					raise ASABIrisError(
						ErrorCode.INVALID_SERVICE_CONFIGURATION,
						tech_message="Empty message body after trimming.",
						error_i18n_key="Invalid input: {{error_message}}.",
						error_dict={"error_message": "Empty message body after trimming."}
					)

				if not message.isascii():
					L.warning("Message contains non-ASCII characters.")
					raise ASABIrisError(
						ErrorCode.INVALID_SERVICE_CONFIGURATION,
						tech_message="Message contains non-ASCII characters.",
						error_i18n_key="Invalid input: {{error_message}}.",
						error_dict={"error_message": "Message contains non-ASCII characters."}
					)

				# Split long messages into SMS-sized parts
				message_parts = self.split_message(message)

				for part in message_parts:
					time_now, sul, auth = self.generate_auth_params(password)
					params = {
						"action": "send_sms",
						"login": login,
						"time": time_now,
						"sul": sul,
						"auth": auth,
						"number": phone,
						"message": part,
					}

					try:
						async with session.get(api_url, params=params) as resp:
							response_body = await resp.text()
					except aiohttp.ClientError as err:
						L.error("Network error while sending SMS: {}".format(err))
						raise ASABIrisError(
							ErrorCode.SERVER_ERROR,
							tech_message="Network error while calling SMSBrana.cz.",
							error_i18n_key="Error occurred while sending SMS. Reason: '{{error_message}}'.",
							error_dict={"error_message": str(err)}
						) from err

					if resp.status != 200:
						L.warning("SMSBrana.cz responded with {}: {}".format(resp.status, response_body))
						raise ASABIrisError(
							ErrorCode.SERVER_ERROR,
							tech_message="SMSBrana.cz responded with '{}': '{}'".format(resp.status, response_body),
							error_i18n_key="Error occurred while sending SMS. Reason: '{{error_message}}'.",
							error_dict={"error_message": response_body}
						)

					# Parse XML to extract error code safely
					try:
						root = ET.fromstring(response_body)
						err_node = root.find("err")
						err_code = err_node.text.strip() if (err_node is not None and err_node.text) else None
						if err_code is None:
							raise ValueError("Missing <err> code in response.")
						custom_message = self.ERROR_CODE_MAPPING.get(err_code, "Unknown error occurred.")
					except (ET.ParseError, ValueError) as err:
						custom_message = "Failed to parse response from SMSBrana.cz."
						L.warning("Invalid XML response: {}".format(response_body))
						raise ASABIrisError(
							ErrorCode.SERVER_ERROR,
							tech_message="Failed to parse response from SMSBrana.cz.",
							error_i18n_key="Error occurred while sending SMS. Reason: '{{error_message}}'.",
							error_dict={"error_message": custom_message}
						) from err

					if err_code != "0":
						L.warning("SMS delivery failed. Response: {}".format(response_body))
						raise ASABIrisError(
							ErrorCode.SERVER_ERROR,
							tech_message="SMS delivery failed. Error code: {}. Message: {}".format(
								err_code, custom_message
							),
							error_i18n_key="Error occurred while sending SMS. Reason: '{{error_message}}'.",
							error_dict={"error_message": custom_message}
						)

					L.log(asab.LOG_NOTICE, "SMS part sent successfully")

		return True
