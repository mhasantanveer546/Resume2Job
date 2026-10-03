import json,uuid,time,hashlib,secrets
from collections import defaultdict,deque
from contextlib import asynccontextmanager
from fastapi import FastAPI,UploadFile,File,HTTPException,Request,Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from . import config,engine as E,agents as AG,analysis as A,store,llm
from .schemas import CandidateProfile,JobPreferences,TextResume,AnalysisRequest
ROOT=config.ROOT
@asynccontextmanager
async def lifespan(app):
    with store.connection():pass
    yield
app=FastAPI(title='Resume2Job',version=config.VERSION,lifespan=lifespan)
limits=defaultdict(deque)
@app.middleware('http')
async def safety(request,call_next):
    owner=request.cookies.get('r2j_session')
    if not owner or len(owner)!=64:owner=secrets.token_hex(32)
    request.state.owner=owner
    if request.url.path.startswith('/api/') and request.method not in ('GET','HEAD'):
        origin=request.headers.get('origin')
        if origin and origin!=str(request.base_url).rstrip('/'):
            return JSONResponse({'error':{'code':'origin','message':'Cross-origin writes are disabled.'}},403)
        ip=request.client.host if request.client else 'local';now=time.monotonic();q=limits[ip]
        while q and now-q[0]>60:q.popleft()
        if len(q)>=120:return JSONResponse({'error':{'code':'rate_limit','message':'Too many requests. Please wait a minute.'}},429)
        q.append(now)
        if len(limits)>1000:
            for key in list(limits):
                if not limits[key] or now-limits[key][-1]>60:limits.pop(key,None)
        try:size=int(request.headers.get('content-length',0))
        except ValueError:size=0
        if size>config.MAX_BYTES+65536:return JSONResponse({'error':{'code':'file_too_large','message':'Request exceeds the 5 MB upload limit.'}},413)
    response=await call_next(request)
    response.set_cookie('r2j_session',owner,httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=config.RETENTION)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.url.path in ('/docs','/redoc'):
        response.headers['Content-Security-Policy']="default-src 'self' https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; frame-ancestors 'none'"
    if request.url.path.startswith('/api/'):response.headers['Cache-Control']='no-store'
    return response
@app.exception_handler(E.UserError)
async def user_error(_,e):return JSONResponse({'error':{'code':e.code,'message':e.msg}},400)
@app.exception_handler(HTTPException)
async def http_error(_,e):return JSONResponse({'error':{'code':str(e.status_code),'message':str(e.detail)}},e.status_code)
@app.exception_handler(RequestValidationError)
async def validation_error(_,e):return JSONResponse({'error':{'code':'validation','message':'Check the supplied fields, lengths and numeric values.'}},422)
@app.exception_handler(Exception)
async def unknown_error(_,e):return JSONResponse({'error':{'code':'server_error','message':'Unable to complete this step. Your saved profile is unchanged; retry.'}},500)
def public(p):return {k:v for k,v in p.items() if k!='text'}
def session(i,r):return store.get(i,r.state.owner)
def save(i,r,d):store.put(i,r.state.owner,d)
def make_resume(text,request):
    with llm.budget(15):p=AG.resume_analyzer(text,E.parse_profile(text))
    CandidateProfile.model_validate(p)
    i=store.create(request.state.owner,{'profile':p,'prefs':{},'analyses':{}})
    return {'id':i,'profile':public(p)}
@app.post('/api/resumes')
async def upload(request:Request,file:UploadFile=File(...)):
    try:
        if not (file.filename or '').lower().endswith('.pdf'):raise E.UserError('unsupported_file','Please upload a .pdf file.')
        data=await file.read(config.MAX_BYTES+1)
        text=await run_in_threadpool(E.extract_text,data)
        return await run_in_threadpool(make_resume,text,request)
    finally:await file.close()
@app.post('/api/resumes/text')
def paste(body:TextResume,request:Request):
    if len(body.text.strip())<50:raise E.UserError('no_text','Enter at least 50 characters of resume content.')
    return make_resume(body.text,request)
@app.get('/api/resumes/{i}/profile')
def profile(i:str,request:Request):
    d=session(i,request);return {'profile':public(d['profile']),'preferences':d['prefs']}
@app.post('/api/resumes/{i}/profile/extract')
def extract(i:str,request:Request):
    # Upload already extracts once; return cached extraction, never overwrite user edits.
    return profile(i,request)
@app.put('/api/resumes/{i}/profile')
def update(i:str,body:CandidateProfile,request:Request):
    d=session(i,request);d['profile'].update(body.model_dump());d['profile']['skills']=E.normalize(body.skills)
    d['profile']['evidence']={s:['User confirmed in profile editor'] for s in d['profile']['skills']}
    d['analyses']={};save(i,request,d);return public(d['profile'])
@app.put('/api/resumes/{i}/preferences')
def preferences(i:str,body:JobPreferences,request:Request):
    d=session(i,request);d['prefs']=body.model_dump()
    d['profile']['skills']=E.normalize(d['profile']['skills']+body.extra_skills)
    d['analyses']={};save(i,request,d);return d['prefs']
@app.post('/api/resumes/{i}/matches')
def matches(i:str,request:Request):
    d=session(i,request);return {'jobs':AG.explain_matches(E.rank(d['profile'],d['prefs'])), 'dataset_size':len(E.JOBS),'source':'Local snapshot + explicitly labeled synthetic demo roles. Not a live search.'}
def get_job(jid):
    j=next((j for j in E.JOBS if j['id']==jid),None)
    if not j:raise HTTPException(404,'Job not found.')
    return j
@app.get('/api/jobs/{jid}')
def job_detail(jid:int):return get_job(jid)
@app.get('/api/resumes/{i}/jobs/{jid}')
def legacy_detail(i:str,jid:int,request:Request):
    d=session(i,request);j=get_job(jid);return {'job':j,'analysis':E.initial_analysis(d['profile'],j)}
def perform_analysis(i,jid,request):
    d=session(i,request);j=get_job(jid)
    signature=hashlib.sha256(json.dumps([d['profile'],d['prefs'],j,config.VERSION,config.WEIGHTS,__import__('os').getenv('LLM_MODEL',''),__import__('os').getenv('LLM_BASE_URL','')],sort_keys=True).encode()).hexdigest()
    cached=d.get('analyses',{}).get(str(jid))
    if cached and cached['signature']==signature:return cached['result']|{'cached':True}
    with llm.budget(38):result=A.analyze(d['profile'],j)
    result.update({'id':f'{i}:{jid}','resume_id':i,'job_id':jid,'cached':False})
    # A concurrent edit must not be overwritten by a slow analysis.
    fresh=session(i,request)
    if fresh['profile']!=d['profile'] or fresh['prefs']!=d['prefs']:raise HTTPException(409,'Profile changed during analysis. Please retry.')
    fresh.setdefault('analyses',{})[str(jid)]={'signature':signature,'result':result};save(i,request,fresh);return result
@app.post('/api/resumes/{i}/jobs/{jid}/analyze')
def analyze(i:str,jid:int,request:Request):return perform_analysis(i,jid,request)
@app.post('/api/analyses')
def new_analysis(body:AnalysisRequest,request:Request):return perform_analysis(body.resume_id,body.job_id,request)
def split_analysis(aid):
    try:i,jid=aid.rsplit(':',1);return i,int(jid)
    except ValueError:raise HTTPException(404,'Analysis not found.')
@app.get('/api/analyses/{aid}')
def fetch_analysis(aid:str,request:Request):
    i,jid=split_analysis(aid);d=session(i,request);a=d.get('analyses',{}).get(str(jid))
    if not a:raise HTTPException(404,'Analysis not found or invalidated by edits.')
    return a['result']|{'cached':True}
@app.post('/api/resumes/{i}/jobs/{jid}/improve')
def improve(i:str,jid:int,request:Request):
    d=session(i,request)
    with llm.budget(15):return A.improve(d['profile'],get_job(jid),A.keyword_analysis(d['profile'],get_job(jid)))
@app.post('/api/analyses/{aid}/improve')
def improve_analysis(aid:str,request:Request):
    i,jid=split_analysis(aid);fetch_analysis(aid,request);return improve(i,jid,request)
@app.delete('/api/resumes/{i}')
def delete(i:str,request:Request):store.delete(i,request.state.owner);return {'deleted':True}
@app.get('/api/health')
def health():
    import os
    return {'status':'ok','version':config.VERSION,'jobs':len(E.JOBS),'synthetic_jobs':sum(bool(j.get('synthetic')) for j in E.JOBS),'llm':'configured (checked on use)' if llm.configured() else 'deterministic mode','llm_last_status':llm.last_status,'model':os.getenv('LLM_MODEL',''),'skills':len(E.SK),'weights':config.WEIGHTS}
@app.get('/api/demo/{persona}')
def demo(persona:str):
    if persona not in ('ayesha','omar','sara','bilal','mina'):raise HTTPException(404,'Demo not found.')
    return {'text':(ROOT/'tests/fixtures'/f'{persona}.txt').read_text(encoding='utf-8')}
app.mount('/',StaticFiles(directory=ROOT/'static',html=True))
