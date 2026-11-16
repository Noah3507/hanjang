"""v3 second-stage routes; all artifacts use existing session/TTL protection."""
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from app.api.uploads import owner
from app.schemas.designs import Strategy, DesignRequest, DesignResponse, DesignEdit, DesignSnapshot
from app.services.uploads import UploadError

router=APIRouter(tags=['designs-v3'])
BASE='/jobs/{job_id}/designs/{strategy}'


def dispatch(store,background,user,job,task):
    if task:
        try:background.add_task(store.finish,user,job,task)
        except Exception:
            with store.renders.locked():store.renders.slot.cancel(task[4])
            raise UploadError(503,'V3_DISPATCH_FAILED','작업을 예약하지 못했습니다.') from None


@router.post(BASE,status_code=202,response_model=DesignResponse)
def start(job_id:str,strategy:Strategy,body:DesignRequest,request:Request,response:Response,background:BackgroundTasks,user:str=Depends(owner)):
    store=request.app.state.design_store
    result,task=store.start(user,job_id,strategy,body)
    dispatch(store,background,user,job_id,task)
    response.headers['Cache-Control']='no-store'
    response.headers['Location']=f'/api/v1/jobs/{job_id}/designs/{strategy}'
    return result


@router.get(BASE,response_model=DesignResponse)
def get(job_id:str,strategy:Strategy,request:Request,response:Response,user:str=Depends(owner)):
    response.headers['Cache-Control']='no-store'
    return request.app.state.design_store.get(user,job_id,strategy)


@router.patch(BASE+'/candidates/{candidate_id}',status_code=202,response_model=DesignResponse)
def edit(job_id:str,strategy:Strategy,candidate_id:str,body:DesignEdit,request:Request,response:Response,background:BackgroundTasks,user:str=Depends(owner)):
    store=request.app.state.design_store
    result,task=store.edit(user,job_id,strategy,candidate_id,body)
    dispatch(store,background,user,job_id,task)
    response.headers['Cache-Control']='no-store'
    return result


@router.post(BASE+'/ranking',response_model=DesignResponse)
def rank(job_id:str,strategy:Strategy,body:DesignSnapshot,request:Request,response:Response,user:str=Depends(owner)):
    response.headers['Cache-Control']='no-store'
    return request.app.state.design_store.rank(user,job_id,strategy,body)


@router.get(BASE+'/ranking',response_model=DesignResponse)
def ranking(job_id:str,strategy:Strategy,request:Request,response:Response,user:str=Depends(owner)):
    return get(job_id,strategy,request,response,user)


@router.get(BASE+'/diagnostics')
def diagnostics(job_id:str,strategy:Strategy,request:Request,response:Response,user:str=Depends(owner)):
    state=get(job_id,strategy,request,response,user)
    return {'revision':state.revision,'snapshot':state.snapshot,'is_current':state.is_current,
            'results':state.diagnostics,'intentional_overlays_are_not_suppressed':True}


@router.get(BASE+'/candidates/{candidate_id}/download')
def download(job_id:str,strategy:Strategy,candidate_id:str,request:Request,format:Literal['png','pdf'],
             expected_revision:int=Query(ge=1),expected_snapshot:str=Query(pattern=r'^[a-f0-9]{64}$'),user:str=Depends(owner)):
    data,mime,name=request.app.state.design_store.download(user,job_id,strategy,candidate_id,
        DesignSnapshot(expected_revision=expected_revision,expected_snapshot=expected_snapshot),format)
    return Response(data,media_type=mime,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
        'Content-Disposition':f'attachment; filename="{name}"'})
