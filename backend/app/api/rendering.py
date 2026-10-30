from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from app.api.uploads import owner
from app.schemas.rendering import RenderRequest, RenderResponse

router = APIRouter(tags=['rendering'])

@router.post('/jobs/{job_id}/rendering', status_code=202, response_model=RenderResponse)
def start(job_id: str, body: RenderRequest, request: Request, response: Response,
          background: BackgroundTasks, user: str = Depends(owner)):
    store = request.app.state.render_store
    result, task = store.start(user, job_id, body)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Location'] = result.status_url
    if task: background.add_task(store.finish, user, job_id, task)
    return result

@router.get('/jobs/{job_id}/rendering', response_model=RenderResponse)
def get(job_id: str, request: Request, response: Response, user: str = Depends(owner)):
    response.headers['Cache-Control'] = 'no-store'
    return request.app.state.render_store.get(user, job_id)
