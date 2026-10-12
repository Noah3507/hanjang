from fastapi import APIRouter, Depends, File, Header, Request, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from app.schemas.upload import DraftResponse, InputDraft, SessionResponse, UploadResponse
from app.services.uploads import MAX_BYTES, PrivateUploadStore, UploadError, validate_image

router = APIRouter(tags=["uploads"])


def store(request: Request) -> PrivateUploadStore:
    return request.app.state.upload_store


def owner(request: Request, x_hanjang_session: str | None = Header(default=None)) -> str:
    return store(request).authenticate(x_hanjang_session)


@router.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session(response: Response, storage: PrivateUploadStore = Depends(store)):
    token, expiry = storage.create_session()
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(session_token=token, expires_at=expiry)


@router.post("/uploads", response_model=UploadResponse, status_code=201)
async def upload_photo(
    request: Request, response: Response, photo: UploadFile = File(...),
    user: str = Depends(owner), storage: PrivateUploadStore = Depends(store),
):
    try:
        form = await request.form()
        if len(form.multi_items()) != 1:
            raise UploadError(422, "INVALID_INPUT", "사진 한 장만 전송해 주세요.")
        data = await photo.read(MAX_BYTES + 1)
        dimensions = await run_in_threadpool(validate_image, data, photo.content_type)
        result = await run_in_threadpool(storage.save, user, data, dimensions)
        response.headers["Cache-Control"] = "no-store"
        return result
    finally:
        await photo.close()


@router.put("/jobs/{job_id}/input", response_model=DraftResponse)
def save_input(
    job_id: str, draft: InputDraft, response: Response,
    user: str = Depends(owner), storage: PrivateUploadStore = Depends(store),
):
    response.headers["Cache-Control"] = "no-store"
    return storage.save_draft(user, job_id, draft)


@router.get("/jobs/{job_id}/input", response_model=DraftResponse)
def get_input(
    job_id: str, response: Response,
    user: str = Depends(owner), storage: PrivateUploadStore = Depends(store),
):
    response.headers["Cache-Control"] = "no-store"
    return storage.get_draft(user, job_id)


@router.get("/assets/{asset_id}")
def get_original(
    asset_id: str, user: str = Depends(owner), storage: PrivateUploadStore = Depends(store),
):
    data, mime = storage.read_asset(user, asset_id)
    return Response(data, media_type=mime, headers={
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": 'inline; filename="original.' + ("jpg" if mime == "image/jpeg" else "png") + '"',
    })
