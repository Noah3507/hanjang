from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from app.api.uploads import owner
from app.schemas.analysis import AnalysisRequest, AnalysisResponse

router = APIRouter(tags=['product photo analysis'])

@router.post('/jobs/{job_id}/photo-analysis', status_code=202, response_model=AnalysisResponse)
def start(job_id: str, body: AnalysisRequest, request: Request, response: Response,
          background: BackgroundTasks, user: str = Depends(owner)):
    storage = request.app.state.analysis_store
    result, run = storage.start(user, job_id, body.expected_asset_id)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Location'] = result.status_url
    if run:
        background.add_task(storage.finish, user, job_id, body.expected_asset_id)
    return result

@router.get('/jobs/{job_id}/photo-analysis', response_model=AnalysisResponse)
def get(job_id: str, request: Request, response: Response, user: str = Depends(owner)):
    response.headers['Cache-Control'] = 'no-store'
    return request.app.state.analysis_store.get(user, job_id)
