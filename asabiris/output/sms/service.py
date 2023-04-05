import datetime
import logging
import secrets
import aiohttp
import asab
import passlib.hash

from ...output_abc import OutputABC
from ...exceptions import SMSDeliveryError
#

L = logging.getLogger(__name__)


#


class SMSOutputService(asab.Service, OutputABC):
	"""
	SMSBrana API documentation https://www.smsbrana.cz/dokumenty/SMSconnect_dokumentace.pdf
	Example smsbrana.cz API response:
	```xml
	<?xml version='1.0' encoding='utf-8'?>
	<result>
	<err>10</err>
	</result>
	```
	#   tree = xml.etree.ElementTree.ElementTree(xml.etree.ElementTree.fromstring(xmlstring))
	"""

	Channel = "sms"

	ConfigDefaults = {  # If True, messages are not sent, but rather printed to the log
		"login": "",
		"password": "",
		"url": "https://api.smsbrana.cz/smsconnect/http.php",
		# smsbrana provides a backup server: https://api-backup.smsbrana.cz/smsconnect/http.php
		"timestamp_format": "%Y%m%dT%H%M%S",  # Use STARTTLS protocol
	}

	def __init__(self, app, service_name="SMSOutputService"):
		super().__init__(app, service_name)
		self.Login = asab.Config.get("login")
		self.Password = asab.Config.get("password")
		self.TimestampFormat = asab.Config.get("timestamp_format")
		self.URL = asab.Config.get("url")

	async def send(self, sms_data):
		if sms_data['phone'] is None or sms_data['phone'] == "":
			L.error("Empty or no phone number specified.")
			raise RuntimeError("Empty or no phone number specified.")

		if isinstance(sms_data['message_body'], str):
			message_list = [sms_data['message_body']]
		else:
			message_list = sms_data['message_body']

		for text in message_list:
			url_params = {
				"action": "send_sms",
				"login": self.Login,
				"time": None,
				"salt": None,
				"auth": None,
				"number": sms_data['phone'],
				"message": text
			}

			time = datetime.datetime.now(datetime.timezone.utc).strftime(self.TimestampFormat)
			salt = secrets.token_urlsafe(16)
			auth = passlib.hash.hex_md5.hash(self.Password + time + salt)
			url_params["time"] = time
			url_params["salt"] = salt
			url_params["auth"] = auth

			async with aiohttp.ClientSession() as session:
				async with session.get(self.URL, params=url_params) as resp:
					if resp.status != 200:
						L.error("SMSBrana.cz responsed with {}".format(resp), await resp.text())
						raise SMSDeliveryError(phone_number=sms_data['phone'])
					response_body = await resp.text()

			if "<err>0</err>" not in response_body:
				L.error("SMS delivery failed. SMSBrana.cz response: {}".format(response_body))
				raise SMSDeliveryError(phone_number=sms_data['phone'])
			else:
				L.log(asab.LOG_NOTICE, "SMS sent")
		return True
