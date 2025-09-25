"""Core application exceptions."""


class ScorpiusBaseException(Exception):
    """Base exception class for Scorpius application."""

    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code = code
        super().__init__(self.message)


class ValidationError(ScorpiusBaseException):
    """Raised when data validation fails."""

    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class NotFoundError(ScorpiusBaseException):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str):
        super().__init__(message, "NOT_FOUND")


class BusinessLogicError(ScorpiusBaseException):
    """Raised when business logic rules are violated."""

    def __init__(self, message: str):
        super().__init__(message, "BUSINESS_LOGIC_ERROR")


class AuthenticationError(ScorpiusBaseException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTHENTICATION_ERROR")


class AuthorizationError(ScorpiusBaseException):
    """Raised when authorization fails."""

    def __init__(self, message: str = "Access denied"):
        super().__init__(message, "AUTHORIZATION_ERROR")


class ProcessingError(ScorpiusBaseException):
    """Raised when document processing fails."""

    def __init__(self, message: str):
        super().__init__(message, "PROCESSING_ERROR")


class ExternalServiceError(ScorpiusBaseException):
    """Raised when external service calls fail."""

    def __init__(self, message: str, service: str = None):
        self.service = service
        super().__init__(message, "EXTERNAL_SERVICE_ERROR")


class ConfigurationError(ScorpiusBaseException):
    """Raised when application configuration is invalid."""

    def __init__(self, message: str):
        super().__init__(message, "CONFIGURATION_ERROR")


class RateLimitError(ScorpiusBaseException):
    """Raised when rate limits are exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, "RATE_LIMIT_ERROR")