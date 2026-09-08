import logging
import hashlib
import datetime
import secrets
import re

import xml.etree.ElementTree as ET

import asab
import aiohttp
import pytz

from ...output_abc import OutputABC
from ...errors import ASABIrisError, ErrorCode
from ...audit import AuditLogger
from ..retry import DeliveryError, RetryPolicy, http_request

L = logging.getLogger(__name__)

asab.Config.add_defaults({
	'sms': {
		"login": "",
		"password": "",
		"timestamp_format": "%Y%m%dT%H%M%S",
		"api_url": "https://api.smsbrana.cz/smsconnect/http.php",
		# Optional keys (added to avoid NoOptionError and allow sane fallbacks)
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
			L.warning(
				"Invalid timezone in [sms]; using Europe/Prague. Set timezone to a valid IANA name.",
				struct_data={"timezone": tz_name},
			)
			self.TimeZone = pytz.timezone("Europe/Prague")

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

	def _normalize_message(self, s: str) -> str:
		"""
		Clean and compact a message for SMS while preserving line breaks:
		- collapse spaces/tabs but keep '\n'
		- normalize common separators and punctuation spacing without crossing lines
		"""
		if s is None:
			return ""

		# Normalize CRLF/CR to LF, keep actual newlines
		s = str(s).replace("\r\n", "\n").replace("\r", "\n")

		# Collapse runs of spaces/tabs but DO NOT touch '\n'
		# [^\S\n] == whitespace except newline
		s = re.sub(r"[^\S\n]+", " ", s)

		# Add a space after labels like "Severity:" but don't touch times "12:34" or URLs "http://"
		s = re.sub(r"(?<=[A-Za-z])\s*:\s*(?!//)(?=\S)", ": ", s)

		# Normalize hyphen spacing only if there's already whitespace on at least one side
		# (so IDs like ALZA-000092 stay intact)
		s = re.sub(r"(?<=\S)(?:\s+-\s*|\s*-\s+)(?=\S)", " - ", s)

		# Remove leading/trailing spaces on each line but keep line structure
		s = "\n".join(line.strip() for line in s.split("\n"))

		# Optional: collapse multiple blank lines -> single blank line
		s = re.sub(r"\n{3,}", "\n\n", s)

		return s

	def _split_message_words(self, message: str, first_len: int = 160, next_len: int = 153, prefix_template: str = None, include_single: bool = False):
		"""
		Split message on word boundaries for SMS segment sizes.
		Supports optional part numbering via prefix_template, e.g. "{i}/{n} ".
		Preserves '\n'. Uses an iterative pass so the prefix length is accounted for
		even when numbering a single-part message.
		"""
		# Tokens that keep newlines as their own tokens
		tokens = re.findall(r"\S+(?:[ \t]+|(?=\n)|$)|\n", message)

		def pack(lim_first, lim_next):
			segs = []
			lim = lim_first
			cur = ""
			for tok in tokens:
				# If token itself is longer than the limit, hard-split the token
				if len(tok) > lim:
					if cur:
						segs.append(cur.rstrip(" "))  # don't strip '\n'
						cur = ""
						lim = lim_next
					start = 0
					while start < len(tok):
						end = start + lim
						segs.append(tok[start:end].rstrip(" "))
						start = end
						lim = lim_next
					continue

				if len(cur) + len(tok) <= lim:
					cur += tok
				else:
					segs.append(cur.rstrip(" "))
					cur = tok
					lim = lim_next

			if cur:
				segs.append(cur.rstrip(" "))
			return segs

		# First pass without prefixes to estimate part count
		segments = pack(first_len, next_len)

		# If numbering requested and there are multiple parts OR we want 1/1
		if prefix_template and (len(segments) > 1 or include_single):
			# Stabilize n because adding a prefix can increase the part count
			n = len(segments) if len(segments) > 0 else 1
			while True:
				prefix_len = len(prefix_template.format(i=n, n=n))
				segs2 = pack(first_len - prefix_len, next_len - prefix_len)
				n2 = len(segs2) if len(segs2) > 0 else 1
				if n2 == n:
					segments = ["{}{}".format(prefix_template.format(i=i + 1, n=n), seg) for i, seg in enumerate(segs2)]
					break
				n = n2

		return segments

	async def send(self, sms_data):
		"""
		Sends an SMS using either tenant-specific or global SMS settings,
		and falls back to a default phone if none is provided per-call.
		"""
		# 0) Validate message_body presence early
		try:
			effective_tenant = asab.contextvars.Tenant.get()
		except LookupError:
			effective_tenant = None

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
		if effective_tenant:
			login_tenant = None
			password_tenant = None
			api_url_tenant = None

			try:
				conf = self.ConfigService.get_sms_config(effective_tenant)
			except Exception as err:
				L.warning(
					"Failed to load tenant SMS configuration; using global [sms] credentials.",
					struct_data={"tenant": effective_tenant, "error_type": type(err).__name__},
				)
				conf = None

			# Accept tuple/list (3 or 4 items) or dict
			if conf:
				if isinstance(conf, (list, tuple)):
					if len(conf) >= 3:
						login_tenant, password_tenant, api_url_tenant = conf[0], conf[1], conf[2]
						if len(conf) >= 4:
							phone_tenant = _clean(conf[3])
					else:
						L.warning(
							"Tenant SMS configuration tuple is too short; using global [sms] credentials.",
							struct_data={"tenant": effective_tenant},
						)
				elif isinstance(conf, dict):
					login_tenant = conf.get("login")
					password_tenant = conf.get("password")
					api_url_tenant = conf.get("api_url")
					phone_tenant = _clean(conf.get("phone"))
				else:
					L.warning(
						"Tenant SMS configuration has an unexpected format; using global [sms] credentials.",
						struct_data={"tenant": effective_tenant},
					)

			# Override creds if all three tenant values are present
			if login_tenant and password_tenant and api_url_tenant:
				login, password, api_url = login_tenant, password_tenant, api_url_tenant
			else:
				L.warning(
					"Tenant SMS configuration is incomplete; using global [sms] credentials.",
					struct_data={"tenant": effective_tenant},
				)

		phone = next((p for p in (phone_tenant, body_phone) if p), None)

		# 3) Validate that we have a phone number from at least one source
		if not phone:
			L.warning(
				"No SMS recipient phone number configured; set phone in tenant SMS config or in the request body.",
				struct_data={"tenant": effective_tenant},
			)
			raise ASABIrisError(
				ErrorCode.INVALID_SERVICE_CONFIGURATION,
				tech_message="No phone number provided (tenant/api/config).",
				error_i18n_key="Invalid input: {{error_message}}.",
				error_dict={"error_message": "Phone number is required (tenant or request body)."}
			)

		# 4) Validate that we have credentials and URL
		if not (login and password and api_url):
			L.error(
				"SMS service is not configured; set login, password, and api_url in [sms] or tenant configuration.",
				struct_data={"tenant": effective_tenant, "api_url": api_url},
			)
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

		retry = RetryPolicy("smsbrana")

		# 6) Reuse one session with a reasonable timeout
		timeout = aiohttp.ClientTimeout(total=15)
		part_number = 0
		async with aiohttp.ClientSession(timeout=timeout) as session:
			for message in message_list:
				# Clean + normalize
				message = self._normalize_message(str(message))
				if not message:
					raise ASABIrisError(
						ErrorCode.INVALID_SERVICE_CONFIGURATION,
						tech_message="Empty message body after trimming.",
						error_i18n_key="Invalid input: {{error_message}}.",
						error_dict={"error_message": "Empty message body after trimming."}
					)

				if not message.isascii():
					L.warning(
						"SMS message contains non-ASCII characters; use ASCII-only text for SMS delivery.",
						struct_data={"tenant": effective_tenant},
					)
					raise ASABIrisError(
						ErrorCode.INVALID_SERVICE_CONFIGURATION,
						tech_message="Message contains non-ASCII characters.",
						error_i18n_key="Invalid input: {{error_message}}.",
						error_dict={"error_message": "Message contains non-ASCII characters."}
					)
				# Split on word boundaries (first 160 chars, next 153)
				message_parts = self._split_message_words(message, prefix_template="{i}/{n} ", include_single=True)

				for part in message_parts:
					part_number += 1
					user_id = "{}-{}".format(retry.NotificationId, part_number)

					async def send_part():
						# Timestamp and nonce are authentication data, never deduplication IDs.
						time_now, sul, auth = self.generate_auth_params(password)
						params = {
							"action": "send_sms", "login": login, "time": time_now,
							"sul": sul, "auth": auth, "number": phone, "message": part, "user_id": user_id,
						}
						response_body = await http_request(session, "GET", api_url, params=params)
						try:
							root = ET.fromstring(response_body)
							err_code = root.findtext("err")
							if err_code is None:
								raise ValueError("Missing SMS error code")
							err_code = err_code.strip()
						except (ET.ParseError, ValueError) as exc:
							raise DeliveryError("Invalid SMS acknowledgement.", "uncertain") from exc
						if err_code not in ("0", "-1"):
							classification = "temporary" if err_code == "8" else "permanent"
							if err_code not in self.ERROR_CODE_MAPPING or err_code == "1":
								classification = "uncertain"
							raise DeliveryError(
								self.ERROR_CODE_MAPPING.get(err_code, "Unknown SMS error."),
								classification, details={"provider_code": err_code},
							)
					await retry.run(send_part, step="part-{}".format(part_number))

		AuditLogger.log(
			asab.LOG_NOTICE,
			"SMS sent",
			struct_data={"phone": phone, "tenant": effective_tenant},
		)
		return True
