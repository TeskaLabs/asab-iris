import logging
import asab
import hashlib
import datetime
import secrets
import aiohttp
import pytz
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
    def __init__(self, app, service_name="SMSOutputService"):
        super().__init__(app, service_name)
        self.Login = asab.Config.get("sms", "login")
        self.Password = asab.Config.get("sms", "password").strip()
        self.TimestampFormat = asab.Config.get("sms", "timestamp_format")
        self.ApiUrl = asab.Config.get("sms", "api_url")
        self.TimeZone = pytz.timezone('Europe/Prague')

    def generate_auth_params(self):
        time_now = datetime.datetime.now(self.TimeZone).strftime(self.TimestampFormat)  # Ensure Prague time
        sul = secrets.token_urlsafe(16)
        auth_string = "{}{}{}".format(self.Password, time_now, sul)
        auth = hashlib.md5(auth_string.encode('utf-8')).hexdigest()
        return time_now, sul, auth

    async def send(self, sms_data):
        if not sms_data.get('phone'):
            L.error("Empty or no phone number specified.")
            raise ASABIrisError(
                ErrorCode.INVALID_SERVICE_CONFIGURATION,
                tech_message="Empty or no phone number specified.",
                error_i18n_key="Invalid input: {{error_message}}.",
                error_dict={"error_message": "Empty or no phone number specified."}
            )

        if isinstance(sms_data['message_body'], str):
            message_list = [sms_data['message_body']]
        else:
            message_list = sms_data['message_body']

        for text in message_list:
            # Clean the message content
            text = text.replace('\n', ' ').strip()
            if not text.isascii():
                L.warning("Message contains non-ASCII characters.")
                raise ASABIrisError(
                    ErrorCode.INVALID_SERVICE_CONFIGURATION,
                    tech_message="Message contains non-ASCII characters.",
                    error_i18n_key="Invalid input: {{error_message}}.",
                    error_dict={"error_message": "Message contains non-ASCII characters."}
                )

            time_now, sul, auth = self.generate_auth_params()
            params = {
                "action": "send_sms",
                "login": self.Login,
                "time": time_now,
                "sul": sul,
                "auth": auth,
                "number": sms_data['phone'],
                "message": text
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(self.ApiUrl, params=params) as resp:
                    response_body = await resp.text()
                    if resp.status != 200:
                        L.error("SMSBrana.cz responded with {}: {}".format(resp.status, response_body ))
                        raise ASABIrisError(
                            ErrorCode.SERVER_ERROR,
                            tech_message="SMSBrana.cz responded with '{}': '{}'".format(resp.status, response_body ),
                            error_i18n_key="Error occurred while sending SMS. Reason: '{{error_message}}'.",
                            error_dict={"error_message": response_body}
                        )

                    if "<err>0</err>" not in response_body:
                        L.error(f"SMS delivery failed. SMSBrana.cz response: {response_body}")
                        raise ASABIrisError(
                            ErrorCode.SERVER_ERROR,
                            tech_message="SMS delivery failed. SMSBrana.cz response: {}".format(response_body),
                            error_i18n_key="Error occurred while sending SMS. Reason: '{{error_message}}'.",
                            error_dict={"error_message": response_body}
                        )
                    else:
                        L.log(asab.LOG_NOTICE, "SMS sent successfully")

        return True
