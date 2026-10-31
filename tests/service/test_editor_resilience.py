"""Failure injection: no paid API or real models. Real Chromium is separate."""
from copy import deepcopy
from datetime import timedelta
import json
import subprocess
from types import SimpleNamespace
from threading import Event, Thread
import pytest
from test_rendering import service, fake_render, png
from test_editor import prepared, target
from app.schemas.rendering import RenderRequest
from app.schemas.editing import EditRequest
from app.services.export_service import PdfExecution
from app.services.uploads import UploadError, Record, now

@pytest.mark.parametrize('error',[FileNotFoundError,PermissionError,OSError,RuntimeError])
def test_pdf_creation_failure_is_safe_503(service,monkeypatch,error):
    import app.services.export_service as module
    app,c,h,_,b,_,_=service;r,_=prepared(service)
    def fail(*a,**kw):raise error('private/local/node.exe')
    monkeypatch.setattr(module.subprocess,'Popen',fail)
    with pytest.raises(UploadError) as caught:PdfExecution()(b'png')
    assert caught.value.status==503 and caught.value.code=='PDF_FAILED'
    response=c.get(target(b,r)+'/download?format=pdf&expected_revision=1',headers=h)
    assert response.status_code==503 and response.json()['error']['code']=='PDF_FAILED'
    assert 'private/local' not in response.text
    assert c.get(b+'/rendering',headers=h).json()==r

@pytest.mark.parametrize('mode',['nonzero','timeout','bad_json','bad_base64','worker_error','cleanup_error'])
def test_pdf_worker_failures_and_cleanup(monkeypatch,mode):
    import app.services.export_service as module
    calls=[]
    class Process:
        pid=4321
        returncode=1 if mode=='nonzero' else 0
        def communicate(self,*a,**kw):
            calls.append('communicate')
            if mode in ('timeout','cleanup_error'):raise subprocess.TimeoutExpired('private-path',90)
            return ({'bad_json':b'invalid','bad_base64':b'{"pdf":"@!"}','worker_error':b'{"error":"private-path"}'}.get(mode,b'{"pdf":"JVBERi1mYWtl"}'),b'private stderr')
        def poll(self):
            if mode=='cleanup_error':raise OSError('private poll error')
            return None if mode=='timeout' else self.returncode
        def kill(self):calls.append('kill');raise OSError('private cleanup error')
    monkeypatch.setattr(module.subprocess,'Popen',lambda *a,**kw:Process())
    monkeypatch.setattr(module.subprocess,'run',lambda *a,**kw:calls.append('tree cleanup'))
    if module.os.name!='nt':monkeypatch.setattr(module.os,'killpg',lambda *a:calls.append('tree cleanup'))
    with pytest.raises(UploadError) as caught:PdfExecution()(b'png')
    assert caught.value.status==503 and caught.value.code=='PDF_FAILED'
    assert 'private' not in caught.value.message
    if mode=='timeout':assert 'tree cleanup' in calls and 'kill' in calls
    if mode=='cleanup_error':assert 'kill' in calls

@pytest.mark.parametrize('field',['derived','assets','asset_hashes','exports','edited_renders','edits'])
def test_partial_editor_registration_rolls_back(service,monkeypatch,field):
    app,c,h,m,b,_,raw=service;r,edit=prepared(service)
    storage=app.state.upload_store;record=storage.records[m['job_id']]
    storage.save(storage.authenticate(h['X-Hanjang-Session']),raw,(400,300,'image/png'))
    marker=('old',1,'hash');record.exports[marker]=b'old pdf cache'
    before={n:deepcopy(getattr(record,n)) for n in ('derived','asset_hashes','edited_renders','exports')}
    assets=dict(storage.assets);files={p.name:p.read_bytes() for p in storage.root.iterdir()}
    cls=type(storage) if field=='assets' else Record
    original=cls.__setattr__;injected=[]
    def fail_after_set(self,name,value):
        original(self,name,value)
        if self is (storage if field=='assets' else record) and name==field and not injected:
            injected.append(True);raise RuntimeError('injected after metadata assignment')
    monkeypatch.setattr(cls,'__setattr__',fail_after_set)
    c.patch(target(b,r),headers=h,json=edit)
    assert injected and c.get(b+'/editing',headers=h).json()['status']=='failed'
    assert c.get(b+'/rendering',headers=h).json()==r
    assert all(getattr(record,n)==v for n,v in before.items())
    assert storage.assets==assets and {p.name:p.read_bytes() for p in storage.root.iterdir()}==files
    monkeypatch.setattr(cls,'__setattr__',original)
    c.patch(target(b,r),headers=h,json=edit)
    assert c.get(b+'/editing',headers=h).json()['status']=='completed'
    assert c.get(b+'/rendering',headers=h).json()['revision']>1

def test_file_collision_never_deletes_existing_success(service,monkeypatch):
    import app.services.editor_store as module
    app,c,h,m,b,_,_=service;r,edit=prepared(service)
    store=app.state.editor_store;owner=app.state.upload_store.authenticate(h['X-Hanjang-Session'])
    _,task=store.start(owner,m['job_id'],r['candidates'][0]['candidate_id'],EditRequest.model_validate(edit))
    existing=r['candidates'][0]['png']['asset_id'];path=app.state.upload_store.records[m['job_id']].derived[existing]
    data=path.read_bytes()
    monkeypatch.setattr(module.uuid,'uuid4',lambda:SimpleNamespace(hex=existing))
    store.finish(owner,m['job_id'],task)
    assert path.read_bytes()==data and c.get(b+'/rendering',headers=h).json()==r
    assert c.get(b+'/editing',headers=h).json()['status']=='failed'

def test_pdf_cache_latest_revision_failure_and_expiry(service):
    app,c,h,m,b,_,_=service;r,edit=prepared(service)
    count=[];app.state.export_service.pdf=lambda data:(count.append(1) or b'%PDF-synthetic')
    url=target(b,r)+'/download?format=pdf&expected_revision='
    c.get(url+'1',headers=h);c.get(url+'1',headers=h)
    record=app.state.upload_store.records[m['job_id']]
    assert len(count)==1 and len(record.exports)==1
    def fail(*a):raise RuntimeError('render failed')
    app.state.render_store.executor=fail;c.patch(target(b,r),headers=h,json=edit)
    assert len(record.exports)==1
    app.state.render_store.executor=fake_render;c.patch(target(b,r),headers=h,json=edit)
    revision=c.get(b+'/rendering',headers=h).json()['revision']
    assert not record.exports
    c.get(url+str(revision),headers=h);c.get(url+str(revision),headers=h)
    assert len(count)==2 and {k[1] for k in record.exports}=={revision}
    record.upload.expires_at=now()-timedelta(seconds=1);app.state.upload_store.cleanup()
    assert m['job_id'] not in app.state.upload_store.records
    assert not record.exports
    assert c.get(url+str(revision),headers=h).status_code in (404,410)

def test_pdf_in_flight_cannot_repopulate_old_revision(service):
    app,c,h,_,b,_,_=service;r,edit=prepared(service)
    def change(data):
        c.patch(target(b,r),headers=h,json=edit)
        return b'%PDF-old'
    app.state.export_service.pdf=change
    assert c.get(target(b,r)+'/download?format=pdf&expected_revision=1',headers=h).status_code==409
    assert not app.state.upload_store.records[service[3]['job_id']].exports

@pytest.mark.parametrize('kind',['render','edit'])
def test_abandoned_reservation_retries_and_late_task_is_fenced(service,kind):
    app,c,h,m,b,body,_=service
    renders=app.state.render_store;editor=app.state.editor_store
    owner=app.state.upload_store.authenticate(h['X-Hanjang-Session']);clock=[0.]
    renders.slot.clock=lambda:clock[0]
    if kind=='edit':r,edit=prepared(service);start=lambda:editor.start(owner,m['job_id'],r['candidates'][0]['candidate_id'],EditRequest.model_validate(edit));store=editor
    else:start=lambda:renders.start(owner,m['job_id'],RenderRequest.model_validate(body));store=renders
    _,old=start();clock[0]=31
    # GET performs lazy recovery, before duplicate-cache reuse.
    status=store.get(owner,m['job_id']);assert status.status=='failed' and not renders.active
    _,new=start();token=renders.slot.lease.token
    store.finish(owner,m['job_id'],old)
    assert renders.active and renders.slot.lease.token==token
    store.finish(owner,m['job_id'],new)
    assert not renders.active and store.get(owner,m['job_id']).status=='completed'

@pytest.mark.parametrize('kind',['render','edit'])
def test_running_worker_is_not_reaped_or_double_dispatched(service,kind):
    app,c,h,m,b,body,_=service;renders=app.state.render_store;editor=app.state.editor_store
    owner=app.state.upload_store.authenticate(h['X-Hanjang-Session']);clock=[0.];renders.slot.clock=lambda:clock[0]
    if kind=='edit':r,edit=prepared(service);store=editor;start=lambda:editor.start(owner,m['job_id'],r['candidates'][0]['candidate_id'],EditRequest.model_validate(edit))
    else:store=renders;start=lambda:renders.start(owner,m['job_id'],RenderRequest.model_validate(body))
    entered=Event();release=Event();calls=[]
    def blocking(*args):
        calls.append(1);entered.set();assert release.wait(10)
        return fake_render(*args)
    renders.executor=blocking;_,task=start()
    worker=Thread(target=store.finish,args=(owner,m['job_id'],task));worker.start()
    try:
        assert entered.wait(5);clock[0]=10000
        store.get(owner,m['job_id']);assert renders.active
        assert start()[1] is None
        store.finish(owner,m['job_id'],task) # same token cannot claim twice
        assert len(calls)==1
    finally:release.set();worker.join(10)
    assert not worker.is_alive() and not renders.active
    assert store.get(owner,m['job_id']).status=='completed'

@pytest.mark.parametrize('kind',['render','edit'])
def test_dispatch_registration_failure_releases_slot(service,monkeypatch,kind):
    from starlette.background import BackgroundTasks
    app,c,h,_,b,body,_=service
    if kind=='edit':r,edit=prepared(service)
    original=BackgroundTasks.add_task
    def fail(*a,**kw):raise RuntimeError('private queue details')
    monkeypatch.setattr(BackgroundTasks,'add_task',fail)
    response=c.patch(target(b,r),headers=h,json=edit) if kind=='edit' else c.post(b+'/rendering',headers=h,json=body)
    assert response.status_code==503 and 'private' not in response.text
    assert not app.state.render_store.active
    monkeypatch.setattr(BackgroundTasks,'add_task',original)
    response=c.patch(target(b,r),headers=h,json=edit) if kind=='edit' else c.post(b+'/rendering',headers=h,json=body)
    assert response.status_code==202

@pytest.mark.parametrize('kind',['render','edit'])
def test_interrupted_executor_marks_failed_and_releases_for_retry(service,kind):
    app,c,h,m,b,body,_=service;renders=app.state.render_store;editor=app.state.editor_store
    owner=app.state.upload_store.authenticate(h['X-Hanjang-Session'])
    if kind=='edit':r,edit=prepared(service);store=editor;start=lambda:editor.start(owner,m['job_id'],r['candidates'][0]['candidate_id'],EditRequest.model_validate(edit))
    else:store=renders;start=lambda:renders.start(owner,m['job_id'],RenderRequest.model_validate(body))
    def interrupted(*args):raise SystemExit('simulated worker interruption')
    renders.executor=interrupted;_,task=start()
    with pytest.raises(SystemExit):store.finish(owner,m['job_id'],task)
    assert not renders.active and store.get(owner,m['job_id']).status=='failed'
    renders.executor=fake_render;_,retry=start();store.finish(owner,m['job_id'],retry)
    assert store.get(owner,m['job_id']).status=='completed'

def test_render_publication_registration_failure_rolls_back(service,monkeypatch):
    app,c,h,m,b,body,_=service;record=app.state.upload_store.records[m['job_id']]
    original=Record.__setattr__;fired=[]
    def fail(self,name,value):
        original(self,name,value)
        if self is record and name=='asset_hashes' and not fired:
            fired.append(True);raise OSError('after registration')
    monkeypatch.setattr(Record,'__setattr__',fail)
    c.post(b+'/rendering',headers=h,json=body)
    assert c.get(b+'/rendering',headers=h).json()['status']=='failed'
    assert not record.derived and not record.asset_hashes
    assert set(app.state.upload_store.assets)=={m['asset_id']}
    assert len(list(app.state.upload_store.root.iterdir()))==1
    monkeypatch.setattr(Record,'__setattr__',original)
    assert c.post(b+'/rendering',headers=h,json=body).status_code==202
    assert c.get(b+'/rendering',headers=h).json()['status']=='completed'

def test_render_preflight_failure_does_not_leave_processing_cache(service,monkeypatch):
    app,c,h,_,b,body,_=service
    read=app.state.upload_store.read_asset
    monkeypatch.setattr(app.state.upload_store,'read_asset',lambda *a:(_ for _ in ()).throw(UploadError(404,'RESOURCE_NOT_FOUND','사진 없음')))
    assert c.post(b+'/rendering',headers=h,json=body).status_code==404
    assert not app.state.render_store.active
    assert c.get(b+'/rendering',headers=h).json()['status']=='pending'
    monkeypatch.setattr(app.state.upload_store,'read_asset',read)
    assert c.post(b+'/rendering',headers=h,json=body).status_code==202
    assert c.get(b+'/rendering',headers=h).json()['status']=='completed'
