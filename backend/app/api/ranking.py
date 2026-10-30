from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from app.api.uploads import owner
from app.schemas.ranking import RankingRequest, RankingResponse

router = APIRouter(tags=['ranking'])


@router.post('/jobs/{job_id}/ranking', status_code=202, response_model=RankingResponse)
def start(job_id: str, body: RankingRequest, request: Request, response: Response,
          background: BackgroundTasks, user: str = Depends(owner)):
    store = request.app.state.ranking_store
    result, task = store.start(user, job_id, body)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Location'] = result.status_url
    if task:
        background.add_task(store.finish, user, job_id, task)
    return result


@router.get('/jobs/{job_id}/ranking', response_model=RankingResponse)
def get(job_id: str, request: Request, response: Response, user: str = Depends(owner)):
    response.headers['Cache-Control'] = 'no-store'
    return request.app.state.ranking_store.get(user, job_id)
