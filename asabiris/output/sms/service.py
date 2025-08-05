import logging
import asab
import hashlib
import datetime
import secrets
import aiohttp
import pytz
import xml.etree.ElementTree as ET
from ...output_abc import OutputABC
from ...errors import ASABIrisError, ErrorCode

L = logging.getLogger(__name__)

asab.Config.add_defaults(
    {
        'sms': {
            "login": "",
            "password": "",
            "timestamp_format": "%Y%m%dT%H%M%S",
            "api_url": "https://api.smsbrana.cz/smsconnect/http.php",
        }
    }
)


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
        '12': "SMS is longer than the allowed 459 characters."
    }

    def __init__(self, app, service_name="SMSOutputService"):
        super().__init__(app, service_name)
        self.Login = asab.Config.get("sms", "login")
        self.Password = asab.Config.get("sms", "password").strip()
        self.TimestampFormat = asab.Config.get("sms", "timestamp_format")
        self.ApiUrl = asab.Config.get("sms", "api_url")
        self.TimeZone = pytz.timezone('Europe/Prague')
        raw_phone = asab.Config.get("sms", "phone") or ""
        cleaned  = raw_phone.strip()
        self.global_phone = cleaned if cleaned else None
        # Get tenant configuration service
        self.ConfigService = app.get_service("TenantConfigExtractionService")

    def generate_auth_params(self, password):
        """
        Generates authentication parameters required by the SMS API.
        Uses the correct password based on whether tenant-specific config is used.
        """
        time_now = datetime.datetime.now(self.TimeZone).strftime(self.TimestampFormat)  # Ensure Prague time
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
        # 1) Start with global credentials and optional global default phone
        login, password, api_url = self.Login, self.Password, self.ApiUrl
        phone = sms_data.get("phone") or self.GlobalPhone

        # 2) If tenant is specified, attempt to load tenant creds and phone
        if tenant:
            login_tenant, password_tenant, api_url_tenant, phone_tenant = \
                self.ConfigService.get_sms_config(tenant)

            # Override creds if all three tenant values are present
            if all([login_tenant, password_tenant, api_url_tenant]):
                login = login_tenant
                password = password_tenant
                api_url = api_url_tenant
            else:
                L.warning(
                    "Tenant '%s' SMS config incomplete—using global credentials.",
                    tenant
                )

            # Override phone if tenant default exists
            if phone_tenant:
                phone = phone_tenant
                L.info(
                    "Using tenant '%s' default phone %s",
                    tenant,
                    phone
                )

        # 3) Validate that we have a phone number
        if not phone:
            L.warning("Empty or no phone number specified.")
            raise ASABIrisError(
                ErrorCode.INVALID_SERVICE_CONFIGURATION,
                tech_message="Empty or no phone number specified.",
                error_i18n_key="Invalid input: {{error_message}}.",
                error_dict={"error_message": "Empty or no phone number specified."}
            )

        # 4) Validate that we have credentials and URL
        if not (login and password and api_url):
            L.error("Missing SMS configuration (login, password, or API URL).")
            return

        # 5) Normalize message_body into a list of strings
        if isinstance(sms_data["message_body"], str):
            message_list = [sms_data["message_body"]]
        else:
            message_list = sms_data["message_body"]

        # 6) Iterate over each message, split into parts, and send
        for message in message_list:
            # Clean message
            message = message.replace("\n", " ").strip()

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
                    "message": part
                }

                async with aiohttp.ClientSession() as session:
                    async with session.get(api_url, params=params) as resp:
                        response_body = await resp.text()

                        if resp.status != 200:
                            L.warning(
                                "SMSBrana.cz responded with %s: %s",
                                resp.status, response_body
                            )
                            raise ASABIrisError(
                                ErrorCode.SERVER_ERROR,
                                tech_message=(
                                    "SMSBrana.cz responded with '%s': '%s'"
                                ) % (resp.status, response_body),
                                error_i18n_key=(
                                    "Error occurred while sending SMS. "
                                    "Reason: '{{error_message}}'."
                                ),
                                error_dict={"error_message": response_body}
                            )

                        # Parse XML to extract error code
                        try:
                            root = ET.fromstring(response_body)
                            err_code = root.find("err").text
                            custom_message = self.ERROR_CODE_MAPPING.get(
                                err_code, "Unknown error occurred."
                            )
                        except ET.ParseError:
                            custom_message = "Failed to parse response from SMSBrana.cz."
                            L.warning("Failed to parse XML response: %s", response_body)
                            raise ASABIrisError(
                                ErrorCode.SERVER_ERROR,
                                tech_message="Failed to parse response from SMSBrana.cz.",
                                error_i18n_key=(
                                    "Error occurred while sending SMS. "
                                    "Reason: '{{error_message}}'."
                                ),
                                error_dict={"error_message": custom_message}
                            )

                        if err_code != "0":
                            L.warning("SMS delivery failed. Response: %s", response_body)
                            raise ASABIrisError(
                                ErrorCode.SERVER_ERROR,
                                tech_message=(
                                    "SMS delivery failed. Error code: %s. Message: %s"
                                ) % (err_code, custom_message),
                                error_i18n_key=(
                                    "Error occurred while sending SMS. "
                                    "Reason: '{{error_message}}'."
                                ),
                                error_dict={"error_message": custom_message}
                            )
                        else:
                            L.log(asab.LOG_NOTICE, "SMS part sent successfully")

        return True

