from typing import Literal
from fastapi import APIRouter,BackgroundTasks,Depends,Request,Response,Query
from app.api.uploads import owner
from app.schemas.editing import EditRequest,EditResponse
from app.services.uploads import UploadError

router=APIRouter(tags=['editing'])

@router.patch('/jobs/{job_id}/candidates/{candidate_id}',status_code=202,response_model=EditResponse)
def patch(job_id:str,candidate_id:str,body:EditRequest,request:Request,response:Response,
          background:BackgroundTasks,user:str=Depends(owner)):
    store=request.app.state.editor_store
    result,task=store.start(user,job_id,candidate_id,body)
    response.headers['Cache-Control']='no-store';response.headers['Location']=result.status_url
    if task:
        try:background.add_task(store.finish,user,job_id,task)
        except Exception:
            store.cancel_dispatch(task)
            raise UploadError(503,'EDIT_FAILED','작업을 예약하지 못했습니다. 마지막 성공본은 유지됩니다.') from None
    return result

@router.get('/jobs/{job_id}/editing',response_model=EditResponse)
def get(job_id:str,request:Request,response:Response,user:str=Depends(owner)):
    response.headers['Cache-Control']='no-store'
    return request.app.state.editor_store.get(user,job_id)

@router.get('/jobs/{job_id}/candidates/{candidate_id}/download')
def download(job_id:str,candidate_id:str,request:Request,format:Literal['png','pdf'],
             expected_revision:int=Query(ge=1),user:str=Depends(owner)):
    data,mime,filename=request.app.state.export_service.download(user,job_id,candidate_id,expected_revision,format)
    return Response(data,media_type=mime,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Disposition':filename})
