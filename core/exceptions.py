class BotError(Exception):
    """Base exception for bot errors."""
    pass

class DataFetchError(BotError):
    """Raised when data cannot be fetched."""
    pass

class ExecutionError(BotError):
    """Raised when an order execution fails."""
    pass

class ConfigurationError(BotError):
    """Raised when there's an issue with the configuration."""
    pass
