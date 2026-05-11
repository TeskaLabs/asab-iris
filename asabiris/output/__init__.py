from .smtp.service import EmailOutputService
from .sms.service import SMSOutputService
from .msteams.service import MSTeamsOutputService
from .mattermost.service import MattermostOutputService
try:
	from .ms365.service import M365EmailOutputService
except ModuleNotFoundError:
	M365EmailOutputService = None

try:
	from .slack.service import SlackOutputService
except ModuleNotFoundError:
	SlackOutputService = None

__all__ = [
	"EmailOutputService",
	"MSTeamsOutputService",
	"SMSOutputService",
	"MattermostOutputService",
]

if SlackOutputService is not None:
	__all__.append("SlackOutputService")
if M365EmailOutputService is not None:
	__all__.append("M365EmailOutputService")
