"""Regression suite: original prototype paths plus correctness and failure cases."""
import io,json,time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app import engine as E,analysis as A,agents as AG,store,llm
from app.main import app
from app.schemas import CandidateProfile
FIX=Path(__file__).parent/'fixtures'
def profile(name='ayesha'):return E.parse_profile((FIX/f'{name}.txt').read_text())
def create(c,name='ayesha'):
    r=c.post('/api/resumes/text',json={'text':(FIX/f'{name}.txt').read_text()});assert r.status_code==200,r.text;return r.json()['id']
def pdf(text='Python developer. Built Flask and SQL projects with Git and tests.',pages=1,password=None):
    import pymupdf as fitz
    doc=fitz.open()
    for _ in range(pages):doc.new_page().insert_text((50,70),text)
    return doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256,owner_pw='owner',user_pw=password) if password is not None else doc.tobytes()

def test_taxonomy_aliases_and_boundaries():
    assert {'Python','JavaScript','PostgreSQL','FastAPI'}<=set(E.find_skills('py, JS, postgres, fast api'))
    assert 'Java' not in E.find_skills('JavaScript')
    assert 'Git' not in E.find_skills('digital')
    assert len(E.SK)>=300

def test_work_dates_exclude_education_and_merge_overlap():
    p=E.parse_profile('Test\nEducation\nBS University 2018-2022\nExperience\nDeveloper Jan 2023-Jan 2025\nIntern Jun 2023-Sep 2023\nProjects\nApp 2020-2026')
    assert p['years_experience']==2
    assert profile()['years_experience']==0.2 # month-rounded three-month internship

def test_undated_experience_is_unknown_estimate():
    assert E.parse_profile('Experience\nDeveloper building Python projects without dates')['years_experience']==0

@pytest.mark.parametrize('name',['ayesha','omar','sara','bilal','mina'])
def test_personas_scores_and_gap_invariants(name):
    p=profile(name);CandidateProfile.model_validate(p)
    ranked=E.rank(p,{'include_stretch':True})
    assert ranked and ranked==E.rank(p,{'include_stretch':True})
    for m in ranked:
        assert 0<=m['score']<=100
        assert round(sum(m['breakdown'].values()),1)==m['score']
        j=next(j for j in E.JOBS if j['id']==m['job_id']);g=A.skill_gap(p,j);assert A.verify(p,j,g)==0
        assert set(g['matching'])<=set(p['skills'])&set(j['required'])
        assert set(g['missing'])<=set(j['required'])-set(p['skills'])
        assert set(m['matched'])==set(g['matching'])

def test_strong_vs_weak():
    j=E.JOBS[0]
    def score(n):return next(x['score'] for x in E.rank(profile(n),{'include_stretch':True},limit=500) if x['job_id']==j['id'])
    assert score('omar')>score('mina')+20

def test_filters_and_empty():
    p=profile('omar')
    assert all(x['mode']=='remote' for x in E.rank(p,{'work_mode':'remote'}))
    assert E.rank(p,{'location':'Nonexistent Mars Colony','work_mode':'on-site'})==[]
    assert all(next(j for j in E.JOBS if j['id']==x['job_id'])['min_years']<=3 for x in E.rank(p,{'level':'junior'}))

def test_empty_tfidf_does_not_crash():
    p=profile();p.update(skills=[],projects=[],experience=[],text='the and or')
    assert isinstance(E.rank(p,{'include_stretch':True}),list)

def test_pdf_validation():
    assert 'Python' in E.extract_text(pdf())
    for data,code in [(b'not a pdf','unsupported_file'),(b'%PDF-broken','corrupt_pdf'),(pdf(pages=6),'too_many_pages'),(pdf(password='secret'),'encrypted_pdf'),(pdf(text=''),'no_text'),(b'%PDF-'+b'x'*(5*1024*1024),'file_too_large')]:
        with pytest.raises(E.UserError) as err:E.extract_text(data)
        assert err.value.code==code

def test_pdf_fallback(monkeypatch):
    monkeypatch.setattr(E.pdfplumber,'open',lambda *a,**k:(_ for _ in ()).throw(ValueError('broken')))
    assert 'Python' in E.extract_text(pdf())

def test_verifier_checks_both_job_and_profile():
    p=profile();g={'matching':['Python','HTML','Rust'],'missing':['COBOL','Python'],'preferred_matching':['Flask'],'preferred_missing':['Python'],'partial':[]}
    assert A.verify(p,E.JOBS[0],g)>=4
    assert set(g['matching'])<=set(E.JOBS[0]['required'])&set(p['skills'])

def test_llm_extraction_rejects_fabricated_education_years(monkeypatch):
    monkeypatch.setattr(A,'llm',lambda *a,**k:json.dumps({'skills':['Rust','Python'],'education':['PhD at Fake University'],'experience':['CEO at Acme'],'years_experience':12}))
    p=profile();r=AG.resume_analyzer(p['text'],p)
    assert 'Rust' not in r['skills'] and r['education']==p['education'] and r['years_experience']==p['years_experience']
    assert 'CEO at Acme' not in r['experience']

@pytest.mark.parametrize('payload',['garbage','[]','{"skills":7}','{"skills":[42]}'])
def test_malformed_agent_fallback(monkeypatch,payload):
    monkeypatch.setattr(A,'llm',lambda *a,**k:payload);p=profile();assert AG.resume_analyzer(p['text'],p)==p

def test_implied_quote_does_not_erase_gap(monkeypatch):
    p=profile();quote=p['projects'][0]
    monkeypatch.setattr(A,'llm',lambda *a,**k:json.dumps({'items':[{'skill':'Docker','evidence':quote}]}))
    result=A.analyze(p,E.JOBS[0]);assert 'Docker' in result['skills']['missing'] and 'Docker' not in result['skills']['matching']

def test_rewriter_rejects_metrics_employer_and_claim_changes(monkeypatch):
    p=profile();lines=list(dict.fromkeys(p['experience']+p['projects']))[:6]
    for payload in [['Led Acme and increased revenue 200%']*len(lines),[x.replace('Built','Led')+' using Rust' for x in lines]]:
        monkeypatch.setattr(A,'llm',lambda *a,**k:json.dumps({'items':payload}))
        assert all(i['suggested'] is None for i in A.improve(p,E.JOBS[0],{})['items'])

def test_advisor_bounded_and_grounded(monkeypatch):
    monkeypatch.setenv('LLM_BASE_URL','http://localhost:11434/v1');monkeypatch.setenv('LLM_MODEL','test')
    p=profile();j=E.JOBS[0];g=A.skill_gap(p,j);kw=A.keyword_analysis(p,j);ex=A.experience(p,j,g);rec=A.recommend(p,j,g,kw,ex)
    replies=iter([{'tool':'lookup_learning_resources'},{'final':{'recommendation_ids':['r1','invented']}}])
    monkeypatch.setattr(AG,'llm_json',lambda *a:next(replies));adv,log=AG.advisor(p,j,g,kw,ex,rec)
    assert len(log)==1 and adv['recommendation_ids']==['r1']
    monkeypatch.setattr(AG,'llm_json',lambda *a:{'tool':'get_gap_report'})
    assert len(AG.advisor(p,j,g,kw,ex,rec)[1])==4

def test_resources_are_gap_retrieval():
    from app.retrieval import lookup_learning_resources
    r=lookup_learning_resources(['Docker']);assert r and all('Docker' in x['skills'] for x in r)
    assert lookup_learning_resources(['unknown-skill'])==[]

def test_cloud_llm_blocked(monkeypatch):
    monkeypatch.setenv('LLM_BASE_URL','https://api.example.com/v1');monkeypatch.setenv('LLM_MODEL','test')
    assert llm.generate('sensitive resume') is None
    assert 'blocked' in llm.last_status

def test_api_complete_flow_cache_edit_export_delete(client):
    i=create(client)
    assert client.get(f'/api/resumes/{i}/profile').status_code==200
    assert client.post(f'/api/resumes/{i}/profile/extract').status_code==200
    r=client.post(f'/api/resumes/{i}/matches');assert r.status_code==200 and r.json()['jobs']
    a=client.post('/api/analyses',json={'resume_id':i,'job_id':1});assert a.status_code==200,a.text
    result=a.json();assert not result['cached']
    assert client.post('/api/analyses',json={'resume_id':i,'job_id':1}).json()['cached']
    assert client.get('/api/analyses/'+result['id']).status_code==200
    p=CandidateProfile.model_validate(profile()).model_dump();p['education']=['New user-confirmed degree']
    assert client.put(f'/api/resumes/{i}/profile',json=p).status_code==200
    assert client.get('/api/analyses/'+result['id']).status_code==404
    revised=client.post('/api/analyses',json={'resume_id':i,'job_id':1}).json()
    assert not revised['cached'] and revised['experience']['qualification']['candidate_evidence']==p['education']
    assert client.post('/api/analyses/'+result['id']+'/improve').status_code==200
    assert client.delete(f'/api/resumes/{i}').status_code==200
    assert client.get(f'/api/resumes/{i}/profile').status_code==404

def test_api_pdf_upload(client):
    r=client.post('/api/resumes',files={'file':('sample.pdf',pdf(),'application/pdf')});assert r.status_code==200,r.text
    assert client.post('/api/resumes',files={'file':('a.txt',pdf())}).status_code==400

def test_profile_validation_and_extra_skills_consistency(client):
    i=create(client)
    assert client.put(f'/api/resumes/{i}/profile',json={'skills':['Python'],'years_experience':-1}).status_code==422
    assert client.put(f'/api/resumes/{i}/preferences',json={'work_mode':'teleport'}).status_code==422
    assert client.put(f'/api/resumes/{i}/preferences',json={'extra_skills':['Fast API','Docker']}).status_code==200
    p=client.get(f'/api/resumes/{i}/profile').json()['profile'];assert 'Docker' in p['skills'] and 'FastAPI' in p['skills']
    a=client.post('/api/analyses',json={'resume_id':i,'job_id':1}).json();assert 'Docker' in a['skills']['matching']

def test_ownership_and_expiry(client):
    i=create(client)
    with TestClient(app) as other:
        assert other.get(f'/api/resumes/{i}/profile').status_code==404
        assert other.post('/api/analyses',json={'resume_id':i,'job_id':1}).status_code==404
        other.delete(f'/api/resumes/{i}')
    assert client.get(f'/api/resumes/{i}/profile').status_code==200
    with store.connection() as db:db.execute('UPDATE sessions SET created=? WHERE id=?',(time.time()-90000,i))
    assert client.get(f'/api/resumes/{i}/profile').status_code==404

def test_cross_origin_and_errors(client):
    assert client.post('/api/resumes/text',json={'text':'x'*60},headers={'origin':'https://evil.example'}).status_code==403
    r=client.post('/api/resumes/text',json={'text':' ' *60});assert r.status_code==400 and 'error' in r.json()
    assert client.get('/api/jobs/999999').status_code==404

def test_data_integrity():
    assert len(E.JOBS)>=150 and len({j['id'] for j in E.JOBS})==len(E.JOBS)
    for j in E.JOBS:
        assert set(j['required']+j['preferred'])<=set(E.SK)
        assert j.get('synthetic') or j['source_url'].startswith('https://')
        if not j.get('synthetic'):assert all(E.PAT[s].search(j['description']) for s in j['required']+j['preferred'])

def test_import_script(tmp_path):
    import sys
    sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'));import import_jobs
    jobs=import_jobs.main([str(Path(__file__).parents[1]/'data/sample_import.csv'),'--source','test','--out',str(tmp_path/'jobs.json')])
    assert len(jobs)==2

def test_embedding_load_failure_falls_back(monkeypatch):
    from app import retrieval
    monkeypatch.setenv('EMBEDDING_MODEL_PATH','/nonexistent/model')
    def fail(*args):raise OSError('unavailable')
    monkeypatch.setattr(retrieval,'_model',fail)
    sims,mode=retrieval.job_similarities('Python Flask',E.JOBS)
    assert mode=='TF-IDF fallback' and len(sims)==len(E.JOBS)

def test_local_llm_transport_and_failure(monkeypatch):
    import io
    monkeypatch.setenv('LLM_BASE_URL','http://127.0.0.1:11434/v1');monkeypatch.setenv('LLM_MODEL','installed-model')
    monkeypatch.setattr(llm,'_failed_until',0)
    class Transport:
        def open(self,request,timeout):
            assert request.full_url=='http://127.0.0.1:11434/v1/chat/completions'
            assert json.loads(request.data)['model']=='installed-model'
            assert timeout<=12
            return io.BytesIO(json.dumps({'choices':[{'message':{'content':'{"skills":["Python"]}'}}]}).encode())
    monkeypatch.setattr(llm.urllib.request,'build_opener',lambda *a:Transport())
    assert json.loads(llm.generate('test'))['skills']==['Python']
    class Broken:
        def open(self,*a,**k):raise TimeoutError()
    monkeypatch.setattr(llm.urllib.request,'build_opener',lambda *a:Broken())
    assert llm.generate('test') is None and 'unavailable' in llm.last_status
    assert llm._failed_until>time.monotonic()

def test_senior_titles_excluded_for_juniors():
    results=E.rank(profile('omar'),{'level':'junior'},limit=500)
    assert all(next(j for j in E.JOBS if j['id']==m['job_id'])['seniority']!='senior' for m in results)
