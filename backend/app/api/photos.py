from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from app.api.uploads import owner, store
from app.schemas.photo import PhotoResponse, PhotoSource
from app.services.uploads import PrivateUploadStore

router = APIRouter(tags=["photo processing"])


@router.post("/jobs/{job_id}/photo-processing", response_model=PhotoResponse, status_code=202)
def start(job_id: str, request: Request, response: Response, background: BackgroundTasks,
          user: str = Depends(owner), storage: PrivateUploadStore = Depends(store)):
    response.headers["Cache-Control"] = "no-store"
    state, run = storage.start_photo(user, job_id)
    if run:
        background.add_task(storage.finish_photo, user, job_id, request.app.state.photo_processor)
    return state


@router.get("/jobs/{job_id}/photo-processing", response_model=PhotoResponse)
def get(job_id: str, response: Response, user: str = Depends(owner), storage: PrivateUploadStore = Depends(store)):
    response.headers["Cache-Control"] = "no-store"
    return storage.photo_state(user, job_id)


@router.put("/jobs/{job_id}/photo-source", response_model=PhotoResponse)
def select(job_id: str, body: PhotoSource, response: Response,
           user: str = Depends(owner), storage: PrivateUploadStore = Depends(store)):
    response.headers["Cache-Control"] = "no-store"
    return storage.select_photo(user, job_id, body.photo_source)
