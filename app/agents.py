"""Three bounded LLM responsibilities. Model output cannot supply factual prose unchecked."""
import json,re
from pydantic import ValidationError
from . import engine as E
from .schemas import CandidateProfile,ImpliedSkill,AdvisorFinal

def llm_json(prompt):
    from . import analysis as A
    for _ in range(2):
        out=A.llm(prompt+'\nReturn only valid JSON.')
        if not out:return None
        try:return json.loads(out.strip().removeprefix('```json').removesuffix('```').strip())
        except (ValueError,TypeError):continue
    return None

def resume_analyzer(text,base):
    r=llm_json('Extract skills, education, experience, projects, certifications and achievements as arrays of strings. Every non-skill item must be an EXACT contiguous quote. Do not estimate dates or years. JSON object only.\nDOCUMENT_DATA='+json.dumps(text[:12000]))
    try:model=CandidateProfile.model_validate(r)
    except (ValidationError,TypeError):return base
    result=dict(base);result['llm_used']=True
    for key in ['education','experience','projects','certifications','achievements']:
        quotes=[x for x in getattr(model,key) if x.casefold() in text.casefold()]
        result[key]=list(dict.fromkeys(base.get(key,[])+quotes))[:100]
    # Education dates can never become employment through model categorization.
    result['years_experience']=base['years_experience']
    result['skills']=E.normalize(base['skills']+[x for x in model.skills if x in E.find_skills(text)])
    return result

def implied_skills(p,job,g):
    cands=g['missing']+[x['skill'] for x in g['partial']]
    if not cands:return []
    r=llm_json('Find possible implied skills, never confirmed matches. Return {"items":[{"skill":"one allowed skill","evidence":"exact quote"}]}. Allowed skills: '+json.dumps(cands)+'\nDOCUMENT_DATA='+json.dumps(p['text'][:10000]))
    if not isinstance(r,dict) or not isinstance(r.get('items'),list):return None
    found=[]
    for item in r['items'][:20]:
        try:x=ImpliedSkill.model_validate(item)
        except (ValidationError,TypeError):continue
        if x.skill in cands and x.evidence.casefold() in p['text'].casefold():found.append(x.model_dump()|{'status':'unconfirmed; review evidence'})
    return found

def advisor(p,job,g,kw,ex,rec):
    """The model chooses retrieval tools and prioritizes approved recommendation IDs.
    No model-authored candidate claims are published. Max four tool calls.
    """
    from . import analysis as A
    from .retrieval import lookup_learning_resources
    from .llm import configured
    if not configured():return None,[]
    allowed={x['id']:x for x in rec['items']}
    tools={'get_gap_report':lambda:g,'get_keyword_report':lambda:kw,
      'common_missing_skills':lambda:dict(A.common_missing(p,job).most_common(8)),
      'search_other_jobs':lambda:[{'job_id':r['job_id'],'title':r['title'],'score':r['score']} for r in E.rank(p,{'role':job['title']})[:5]],
      'lookup_learning_resources':lambda:lookup_learning_resources(g['missing']+[x['skill'] for x in g['partial']])}
    history=[];log=[]
    for _ in range(5):
        out=llm_json('Career Advisor: select relevant evidence tools then prioritize approved action IDs. Max 4 tool calls. Reply {"tool":"name"} or {"final":{"recommendation_ids":["id"]}}. Tools: '+json.dumps(list(tools))+'\nAPPROVED_ACTIONS='+json.dumps(list(allowed.values()))+'\nRETRIEVED_DATA='+json.dumps(history)+('\nNo tool calls left. Return final.' if len(log)==4 else ''))
        if not isinstance(out,dict):break
        if 'final' in out:
            try:ids=AdvisorFinal.model_validate(out['final']).recommendation_ids
            except ValidationError:break
            ids=list(dict.fromkeys(x for x in ids if x in allowed))
            if not ids or not log:break
            return {'summary':'Prioritized from verified gaps and retrieved evidence.','priorities':[allowed[x]['action'] for x in ids],'recommendation_ids':ids},log
        tool=out.get('tool')
        if not isinstance(tool,str) or tool not in tools or len(log)>=4:break
        result=tools[tool]();history.append({'tool':tool,'result':result});log.append({'tool':tool,'result':json.dumps(result)[:400]})
    return None,log

def explain_matches(rows,limit=5):
    """Generative AI: LLM writes the 'why' line from score facts only; unsupported skills are rejected."""
    from . import llm
    with llm.budget(30):
        for r in rows[:limit]:
            facts={'title':r['title'],'score':r['score'],'matched':r['matched'],'missing':r['missing']}
            out=llm_json('Write ONE plain sentence (max 30 words) explaining this job match. Use ONLY these facts, mention no other skills. Return {"why":"sentence"}. FACTS='+json.dumps(facts))
            why=out.get('why') if isinstance(out,dict) else None
            if isinstance(why,str) and 10<len(why)<300 and set(E.find_skills(why))<=set(r['matched']+r['missing']):
                r['why']=why;r['why_source']='AI'
    return rows