from .smtp.service import EmailOutputService
from .sms.service import SMSOutputService
from .msteams.service import MSTeamsOutputService
from .ms365.service import M365EmailOutputService

try:
	from .slack.service import SlackOutputService
except ModuleNotFoundError:
	SlackOutputService = None

__all__ = [
	"EmailOutputService",
	"MSTeamsOutputService",
	"SMSOutputService",
	"M365EmailOutputService"
]

if SlackOutputService is not None:
	__all__.append("SlackOutputService")
