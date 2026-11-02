from fastapi import APIRouter,Request,Response
router=APIRouter()

@router.get('/ready',tags=['health'])
def readiness(request:Request,response:Response):
    result=dict(request.app.state.runtime_health.get())
    if request.app.state.cleanup_failed:
        result['status']='not_ready';result['cleanup']='retry_required'
    response.headers['Cache-Control']='no-store'
    response.status_code=200 if result['status']=='ready' else 503
    return result
