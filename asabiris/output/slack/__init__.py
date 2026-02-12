try:
	from .service import SlackOutputService
except ModuleNotFoundError:
	SlackOutputService = None
	__all__ = []
else:
	__all__ = ["SlackOutputService"]
