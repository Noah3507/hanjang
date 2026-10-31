from fastapi import APIRouter,Depends,Request,Response
from app.api.uploads import owner
from app.schemas.diagnostics import DiagnosticsRequest,DiagnosticsResponse

router=APIRouter(tags=['diagnostics'])

@router.post('/jobs/{job_id}/diagnostics',response_model=DiagnosticsResponse)
def run(job_id:str,body:DiagnosticsRequest,request:Request,response:Response,user:str=Depends(owner)):
    response.headers['Cache-Control']='no-store'
    return request.app.state.diagnostics_store.run(user,job_id,body)

@router.get('/jobs/{job_id}/diagnostics',response_model=DiagnosticsResponse)
def get(job_id:str,request:Request,response:Response,user:str=Depends(owner)):
    response.headers['Cache-Control']='no-store'
    return request.app.state.diagnostics_store.get(user,job_id)
