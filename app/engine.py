"""Deterministic extraction and explainable ranking. No numeric LLM scores."""
import re, io, json
from datetime import date
import pdfplumber
from rapidfuzz.fuzz import token_set_ratio
from .config import ROOT, WEIGHTS, MAX_BYTES
from .schemas import Job
class UserError(Exception):
    def __init__(self, code, msg): self.code, self.msg = code, msg
SK = {x['name']:x['aliases'] for x in json.loads((ROOT/'data/taxonomy.json').read_text(encoding='utf-8'))}
PAT = {k:re.compile(r'(?<![\w+#])(?:%s)(?![\w+#])' % '|'.join(re.escape(a) for a in v), re.I) for k,v in SK.items()}
JOBS = [Job.model_validate(x).model_dump() | {k:v for k,v in x.items() if k not in Job.model_fields} for x in json.loads((ROOT/'data/jobs.json').read_text(encoding='utf-8'))]
def find_skills(text): return sorted(k for k,p in PAT.items() if p.search(text))
def normalize(skills):
    aliases={a.lower():k for k,v in SK.items() for a in v}
    return sorted(set(aliases.get(x.strip().lower(),x.strip()) for x in skills if x.strip()))
def extract_text(data):
    if len(data)>MAX_BYTES: raise UserError('file_too_large','PDF must be 5 MB or smaller.')
    if not data.startswith(b'%PDF-'): raise UserError('unsupported_file','Only real PDF files are supported.')
    # Independent preflight rejects even empty-password encryption before either parser.
    import pymupdf as fitz
    try:
        with fitz.open(stream=data,filetype='pdf') as pdf:
            if pdf.is_encrypted or pdf.metadata.get('encryption'): raise UserError('encrypted_pdf','Encrypted PDFs are not supported. Export an unencrypted copy.')
            if len(pdf)>5: raise UserError('too_many_pages','Resume must be 5 pages or fewer.')
            fallback='\n'.join(p.get_text() for p in pdf)
    except UserError: raise
    except Exception as e: raise UserError('corrupt_pdf','Could not read this PDF. Try paste text.') from e
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf: text='\n'.join(p.extract_text() or '' for p in pdf.pages)
    except Exception: text=fallback
    if len(text.strip())<50: text=fallback
    if len(text.strip())<50: raise UserError('no_text','No readable text. Paste your resume text below; scanned PDFs need OCR first.')
    return text[:20000]
HEADINGS={'education':'education','academic background':'education','work experience':'experience','professional experience':'experience','employment':'experience','experience':'experience','projects':'projects','personal projects':'projects','certifications':'certifications','certificates':'certifications','achievements':'achievements','awards':'achievements','skills':'skills','technical skills':'skills','summary':'summary','profile':'summary'}
MONTHS={x:i+1 for i,x in enumerate(['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'])}
DATE_RE=r'(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+)?(?:19|20)\d{2}'
def experience_years(lines):
    intervals=[]; now=date.today(); current=now.year*12+now.month-1
    def month(s,end=False):
        if s.lower() in ('present','current','now'): return current
        y=int(re.search(r'\d{4}',s)[0]); m=MONTHS.get(s[:3].lower(),1)
        return y*12+m-1
    for line in lines:
        for a,b in re.findall('('+DATE_RE+r')\s*(?:-|–|—|to)\s*('+DATE_RE+r'|present|current|now)',line,re.I):
            start,end=month(a),min(month(b,True),current)
            if end>start: intervals.append((start,end))
    merged=[]
    for a,b in sorted(intervals):
        if merged and a<=merged[-1][1]: merged[-1][1]=max(b,merged[-1][1])
        else: merged.append([a,b])
    return round(min(sum(b-a for a,b in merged)/12,60),1)
def parse_profile(text):
    lines=[l.strip() for l in text.splitlines() if l.strip()]; sections={k:[] for k in ['skills','education','experience','projects','certifications','achievements','summary']}; section=None
    for l in lines:
        heading=l.lower().strip(': •-')
        if heading in HEADINGS: section=HEADINGS[heading]; continue
        if section: sections[section].append(l[:500])
        else:
            if re.search(r'university|bachelor|master|college|\bBS\b|\bBSc\b',l,re.I): sections['education'].append(l[:500])
            elif re.search(r'\bintern\b|\bdeveloper\b|\bengineer\b|\banalyst\b',l,re.I): sections['experience'].append(l[:500])
    years=experience_years(sections['experience']); skills=find_skills(text)
    return {**{k:v[:100] for k,v in sections.items() if k not in ('skills','summary')},'skills':skills,'years_experience':years,'seniority':'entry' if years<1 else 'junior' if years<3 else 'mid' if years<6 else 'senior','text':text,'llm_used':False,
        'evidence':{s:[l for l in lines if PAT[s].search(l)][:3] for s in skills},'experience_note':'Estimate from non-overlapping work dates only. Review months and undated work.'}
def _hit(a,b):return len(a&b)/len(a) if a else 1.0
def rank(profile,prefs,limit=20):
    from .retrieval import job_similarities
    skills=set(normalize(profile['skills']+prefs.get('extra_skills',[])))
    # Use reviewed content; removed skills and old text must not silently re-enter matching.
    content=' '.join(sorted(skills)+profile.get('experience',[])+profile.get('projects',[]))
    sims,mode=job_similarities(content,JOBS)
    out=[]
    for j,sim in zip(JOBS,sims):
        if prefs.get('job_type') and j['type']!=prefs['job_type']:continue
        if prefs.get('work_mode') and j['mode']!=prefs['work_mode']:continue
        loc=prefs.get('location','').strip().lower()
        if loc and j['mode']!='remote' and loc not in j['location'].lower():continue
        caps={'entry':2,'junior':3,'mid':6}
        if not prefs.get('include_stretch') and prefs.get('level') in ('entry','junior') and j.get('seniority')=='senior':continue
        if not prefs.get('include_stretch') and j['min_years']>caps.get(prefs.get('level'),100):continue
        req,pre=set(j['required']),set(j['preferred']);gap=max(0,j['min_years']-profile['years_experience'])
        role=prefs.get('role','').strip()
        ratios={'Required skills':_hit(req,skills),'Preferred skills':_hit(pre,skills),'Text similarity':max(0,min(1,float(sim))),
            'Title fit':token_set_ratio(role,j['title'])/100 if role else 0.5,'Experience fit':max(0,1-.33*gap),'Preference fit':1.0}
        bd={k:round(WEIGHTS[k]*v,1) for k,v in ratios.items()}; score=round(sum(bd.values()),1)
        if score<35 and not prefs.get('include_stretch'):continue
        m,miss=sorted(req&skills),sorted(req-skills)
        out.append({'job_id':j['id'],'title':j['title'],'company':j['company'],'location':j['location'],'mode':j['mode'],'score':score,
            'label':'Strong match' if score>=75 else 'Good match' if score>=55 else 'Stretch','breakdown':bd,'weights':WEIGHTS,'matched':m,'missing':miss,
            'why':f'You cover {len(m)} of {len(req)} listed required skills. '+(f"Not evidenced: {', '.join(miss[:3])}." if miss else 'All listed required skills are in your reviewed profile.'),
            'source':j['source'],'source_url':j.get('source_url',''),'synthetic':j.get('synthetic',False),'similarity_mode':mode})
    return sorted(out,key=lambda x:(-x['score'],x['job_id']))[:limit]
def initial_analysis(profile,job):
    s=set(profile['skills']);return {'matching':sorted(set(job['required'])&s),'missing_required':sorted(set(job['required'])-s)}
