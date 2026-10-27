from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from app.api.uploads import owner
from app.schemas.copy import CopyRequest, CopyResponse

router = APIRouter(tags=['copy generation'])

@router.post('/jobs/{job_id}/copy-generation', status_code=202, response_model=CopyResponse)
def start(job_id: str, body: CopyRequest, request: Request, response: Response,
          background: BackgroundTasks, user: str = Depends(owner)):
    storage = request.app.state.copy_store
    result, task = storage.start(user, job_id, body)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Location'] = result.status_url
    if task:
        background.add_task(storage.finish, user, job_id, task)
    return result

@router.get('/jobs/{job_id}/copy-generation', response_model=CopyResponse)
def get(job_id: str, request: Request, response: Response, user: str = Depends(owner)):
    response.headers['Cache-Control'] = 'no-store'
    return request.app.state.copy_store.get(user, job_id)
