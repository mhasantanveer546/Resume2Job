"""Evidence-first gap analysis and recommendations, optional bounded local agents."""
import re,time
from collections import Counter
from . import engine as E
from .llm import generate as llm
from .retrieval import lookup_learning_resources
from .schemas import Analysis
RELATED={'FastAPI':['Flask','Django'],'Flask':['FastAPI','Django'],'Django':['Flask','FastAPI'],'PostgreSQL':['MySQL'],'MySQL':['PostgreSQL'],'Docker':['Kubernetes'],'Kubernetes':['Docker'],'CI/CD':['Git','GitHub Actions'],'React':['JavaScript'],'TypeScript':['JavaScript'],'REST APIs':['Flask','FastAPI','Django']}
def scrub(t):return re.sub(r'[\w.+-]+@[\w-]+\.[\w.]+','[email removed]',t)
def skill_gap(p,job):
    s=set(E.normalize(p['skills']));g={'matching':[],'partial':[],'missing':[],'preferred_matching':[],'preferred_missing':[]}
    for k in job['required']:
        if k in s:g['matching'].append(k)
        else:
            related=[x for x in RELATED.get(k,[]) if x in s]
            if related:g['partial'].append({'skill':k,'evidence':related})
            else:g['missing'].append(k)
    for k in job['preferred']:g['preferred_matching' if k in s else 'preferred_missing'].append(k)
    return g

def keyword_analysis(p,job):
    rows=[]
    for imp,skills in [('must',job['required']),('nice',job['preferred'])]:
        for k in skills:
            pat=E.PAT.get(k,re.compile(r'(?<!\w)'+re.escape(k)+r'(?!\w)',re.I));n=len(pat.findall(p['text']))
            claimed=k in p['skills'];status='present' if n>=2 else 'weak' if n else 'missing'
            rows.append({'keyword':k,'importance':imp,'status':status,'count':n,'suggested_placement':'Relevant project or experience bullet',
                'hint':'Add only after gaining real experience.' if not claimed else 'Use a truthful project example to show this skill.' if n<2 else 'Already present.',
                'requires_real_experience':not claimed})
    return {'coverage':round(100*sum(x['count']>0 for x in rows)/len(rows),1) if rows else 100,'keywords':rows,'note':'Keyword overlap with listed requirements, not a prediction of an ATS decision. Repetition alone does not improve your qualifications.'}

def experience(p,job,g):
    requirement=job.get('education','');edu=p.get('education',[])
    # Equivalence depends on discipline and completion, so never assert degree equivalence.
    qualification={'requirement':requirement or 'No explicit qualification captured','candidate_evidence':edu,
        'status':'review' if requirement and edu else 'not evidenced' if requirement else 'not specified',
        'note':'Check subject, level, completion and any equivalent-experience option against the posting.'}
    return {'required_years':job['min_years'],'candidate_years':p['years_experience'],'gap_years':round(max(0,job['min_years']-p['years_experience']),1),
        'missing_evidence':[x['skill'] for x in g['partial']],'actually_missing':g['missing'],'qualification':qualification,
        'note':'Not evidenced means absent from the reviewed profile, not proof that you lack the skill. Work-date estimates require review.'}

def verify(p,job,g):
    s=set(p['skills']);n=0
    for key,ok in [('matching',s&set(job['required'])),('missing',set(job['required'])-s),('preferred_matching',s&set(job['preferred'])),('preferred_missing',set(job['preferred'])-s)]:
        old=g[key];g[key]=list(dict.fromkeys(x for x in old if x in ok));n+=len(old)-len(g[key])
    keep=[x for x in g['partial'] if x['skill'] in set(job['required'])-s and set(x['evidence'])<=s]
    n+=len(g['partial'])-len(keep);g['partial']=keep
    return n

def common_missing(p,job=None):
    ranked=E.rank(p,{'role':job['title'] if job else ''},limit=20)
    ids={r['job_id'] for r in ranked};return Counter(s for j in E.JOBS if j['id'] in ids for s in j['required'] if s not in p['skills'])

def recommend(p,job,g,kw,ex):
    cm=common_missing(p,job);gaps=list(dict.fromkeys(g['missing']+[x['skill'] for x in g['partial']]+g['preferred_missing']))
    order=sorted(gaps,key=lambda k:(k in g['preferred_missing'],-cm[k],k));items=[]
    def add(category,action,evidence):items.append({'id':f'r{len(items)+1}','category':category,'action':action,'evidence':evidence})
    for k in kw['keywords']:
        if k['keyword'] in p['skills'] and k['status']!='present':add('quick_wins',f"Show {k['keyword']} in a truthful project or experience example.",f"User-confirmed profile skill; resume mentions: {k['count']}.")
    for k in order[:5]:add('learn',f'Learn and demonstrate {k} before claiming it.',f"Listed by selected job; also required in {cm[k]} of up to 20 relevant matches.")
    if order:add('build','Build a small portfolio project using '+', '.join(order[:2])+'. Label it as planned until completed.','Selected job gaps: '+', '.join(order[:2]))
    if ex['gap_years']:add('longer_term',f"Target supervised experience to address the estimated {ex['gap_years']}-year gap.",f"Job asks for {job['min_years']} years; profile estimate is {p['years_experience']}.")
    if job.get('education'):add('longer_term','Review the stated qualification and equivalent-experience options.',job['education'])
    if not items:add('quick_wins','Prepare concrete examples for the listed requirements.','All listed skills and experience are covered by your reviewed profile.')
    resources=lookup_learning_resources(order)
    return {'items':items,'quick_wins':[x['action'] for x in items if x['category']=='quick_wins'],'learn':[{'skill':k,'why':f'Listed in selected job; required in {cm[k]} relevant matches.'} for k in order[:5]],
        'build':[x['action'] for x in items if x['category']=='build'],'resources':resources,'effort':'Small' if len(order)<=1 else 'Medium' if len(order)<=3 else 'Large',
        'experience_note':f"Estimated experience gap: {ex['gap_years']} years. Review the work dates."}

def analyze(p,job):
    from . import agents as AG
    steps=[]
    def step(name,fn,detail):
        t=time.monotonic();r=fn();steps.append({'step':name,'ms':int((time.monotonic()-t)*1000),'detail':detail(r)});return r
    g=step('Agent 2 · Gap Analyst (rules)',lambda:skill_gap(p,job),lambda x:f"{len(x['matching'])} confirmed required skills")
    g['implied']=step('Agent 2 · Gap Analyst (LLM)',lambda:AG.implied_skills(p,job,g),lambda x:'Possible implications only; not counted as matches' if x else 'No verified output; deterministic gaps retained') or []
    # Even a real quote cannot prove the inferred skill. Never erase a gap for an implication.
    step('Verifier (no LLM)',lambda:verify(p,job,g),lambda n:f'{n} unsupported claims removed')
    kw=step('Keyword engine',lambda:keyword_analysis(p,job),lambda x:f"{x['coverage']}% literal coverage")
    ex=step('Experience and qualifications',lambda:experience(p,job,g),lambda x:'Evidence and unknowns reported separately')
    rec=step('Retrieval and grounded recommendations',lambda:recommend(p,job,g,kw,ex),lambda x:f"{len(x['resources'])} relevant local resource chunks retrieved")
    adv,log=step('Agent 3 · Career Advisor (tools)',lambda:AG.advisor(p,job,g,kw,ex,rec),lambda x:f'{len(x[1])} actual tool calls; '+('verified action IDs prioritized' if x[0] else 'deterministic recommendations used'))
    result={'skills':g,'keywords':kw,'experience':ex,'recommendations':rec,'advisor':adv,'tool_log':log,'ai_summary':adv['summary'] if adv else None,'steps':steps}
    Analysis.model_validate(result)
    return result

def improve(p,job,kw):
    """Conservative extractive editing: LLM selects verbatim clauses only.
    Novel paraphrases cannot be mechanically proven true; they are rejected.
    """
    from .agents import llm_json
    lines=list(dict.fromkeys(p.get('experience',[])+p.get('projects',[])))[:6]
    if not lines:return {'items':[],'warning':'No experience or project lines to improve. Add them in Profile.','llm':False}
    result=llm_json('Shorten resume bullets for clarity. Each suggested string MUST be one verbatim contiguous substring of its original. Do not add, reorder, negate or change facts. Return {"items":["string"]}, same order. DOCUMENT_DATA='+__import__('json').dumps(lines))
    suggestions=result.get('items') if isinstance(result,dict) else None
    valid=isinstance(suggestions,list) and len(suggestions)==len(lines)
    items=[]
    for idx,original in enumerate(lines):
        proposed=suggestions[idx] if valid else None
        # Only allow removing formatting/outer whitespace, not qualifying clauses.
        safe=original.strip().lstrip('•*- ').strip()
        accepted=isinstance(proposed,str) and proposed.strip()==safe
        items.append({'original':original,'suggested':safe if not valid or accepted else None,'rejected':[] if not valid or accepted else ['Unverifiable factual change'],'mode':'local AI verified' if accepted else 'formatting only' if not valid else 'rejected'})
    return {'items':items,'llm':valid,'warning':'Only use suggestions that are true for you. Strict mode allows formatting cleanup only; factual paraphrases require human review.'}
