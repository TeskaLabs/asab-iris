"""Small retry helper for explicitly temporary notification failures."""
import asyncio

import asab


asab.Config.add_defaults({
	"notification_retry": {
		"max_attempts": "3",
		"delay": "1",
	}
})


async def retry(operation, is_temporary):
	max_attempts = asab.Config.getint("notification_retry", "max_attempts")
	delay = asab.Config.getfloat("notification_retry", "delay")
	if max_attempts < 1 or delay < 0:
		raise ValueError("Invalid [notification_retry] configuration")

	for attempt in range(1, max_attempts + 1):
		try:
			result = await operation()
		except Exception as error:
			if attempt == max_attempts or not is_temporary(None, error):
				raise
		else:
			if attempt == max_attempts or not is_temporary(result, None):
				return result
		await asyncio.sleep(delay)
