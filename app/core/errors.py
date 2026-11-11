class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code, code = 404, "not_found"


class ConflictError(AppError):
    status_code, code = 409, "conflict"


class ForbiddenError(AppError):
    status_code, code = 403, "forbidden"


class InvalidTransitionError(AppError):
    status_code, code = 422, "invalid_transition"
