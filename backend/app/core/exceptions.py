"""Exceções de domínio da aplicação.

Mapeadas para status HTTP semânticos no exception handler do app.
Nunca expõem stack trace nem mensagens internas de banco.
"""


class AppError(Exception):
    """Erro esperado da aplicação com código legível por máquina."""

    code: str = "APP_ERROR"
    http_status: int = 400

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code
        self.message = message


class NotFoundError(AppError):
    code = "NOT_FOUND"
    http_status = 404

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(f"{resource} not found: {identifier}")
        self.resource = resource
        self.identifier = identifier


class ConflictError(AppError):
    code = "CONFLICT"
    http_status = 409


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    http_status = 422


class ExternalServiceUnavailableError(AppError):
    code = "EXTERNAL_SERVICE_UNAVAILABLE"
    http_status = 502

    def __init__(self, service: str, reason: str = "indisponivel") -> None:
        super().__init__(f"Servico externo indisponivel: {service} ({reason})")
        self.service = service


class UnauthorizedError(AppError):
    code = "UNAUTHORIZED"
    http_status = 401


class ForbiddenError(AppError):
    code = "FORBIDDEN"
    http_status = 403


class ApprovalWindowExpiredError(AppError):
    """Tentativa de reverter auto-approve fora da janela (FEAT-009)."""

    code = "APPROVAL_WINDOW_EXPIRED"
    http_status = 400

    def __init__(self) -> None:
        super().__init__(
            "janela de reversao de auto-approve expirou (ou card nao auto-aprovado)"
        )
