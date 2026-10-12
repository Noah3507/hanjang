from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import uuid

from app.services.uploads import UploadError


def error_response(status: int, code: str, message: str, fields: list | None = None):
    return JSONResponse(status_code=status, headers={"Cache-Control": "no-store"}, content={"error": {
        "code": code, "message": message, "field_errors": fields or [],
        "retryable": status == 503, "request_id": uuid.uuid4().hex,
    }})


async def upload_error(request: Request, error: UploadError):
    return error_response(error.status, error.code, error.message)


async def validation_error(request: Request, error: RequestValidationError):
    # Never echo Pydantic's input/context (may contain user facts or bytes).
    fields = [{"field": ".".join(str(part) for part in item["loc"] if part != "body"),
               "message": "필수 값·길이·형식을 확인해 주세요."} for item in error.errors()]
    return error_response(422, "INVALID_INPUT", "입력값을 확인해 주세요.", fields)
