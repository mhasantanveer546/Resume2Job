"""Optional, one-time public API import. Never called by the application.
API attribution: https://www.arbeitnow.com/terms section 11.
"""
import sys,json,urllib.request,html,re
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.engine import find_skills

def convert(raw,n):
    text=html.unescape(html.unescape(raw['description']))
    text=re.sub(r'</(?:p|li|h\d)>','\n',text);text=re.sub('<[^>]+>',' ',text);text=re.sub(r'[ \t]+',' ',text).strip()
    skills=find_skills(text)
    if not skills:return None
    required=set();preferred=set()
    for line in re.split(r'\n|(?<=[.!?])\s+',text):
        (preferred if re.search(r'preferred|nice.to.have|bonus|a plus|desirable',line,re.I) else required).update(find_skills(line))
    # Heuristic mentions, explicitly marked for review. Do not invent unstated requirements.
    title=raw['title'];years=re.search(r'(\d+)\+?\s*(?:years|yrs)(?:\s+of)?\s+(?:relevant |professional |commercial |work )?experience',text,re.I)
    degree=next((line.strip()[:500] for line in text.splitlines() if re.search(r"bachelor|master.s degree|degree in|equivalent.*experience",line,re.I)),'')
    senior='senior' if re.search(r'senior|lead|principal|head of',title,re.I) else 'entry' if re.search(r'graduate|intern|trainee|apprentice',title,re.I) else 'junior' if 'junior' in title.lower() else 'unknown'
    return {'id':n,'title':title,'company':raw['company_name'],'location':raw.get('location','Unspecified'),
        'mode':'remote' if raw.get('remote') else 'hybrid' if 'hybrid' in text.lower() else 'on-site',
        'type':'internship' if re.search(r'intern|trainee',title,re.I) else 'contract' if 'contract' in ' '.join(raw.get('job_types',[])).lower() else 'full-time',
        'min_years':int(years[1]) if years else 0,'experience_unspecified':not bool(years),'seniority':senior,
        'required':sorted(required),'preferred':sorted(preferred-required),'education':degree,'description':text,
        'source':'Arbeitnow UK — cached public API; requirements auto-extracted, review original',
        'source_url':raw.get('url',''),'synthetic':False,'snapshot_date':datetime.now(timezone.utc).date().isoformat()}
def main():
    jobs=[j for j in json.loads((ROOT/'data/jobs.json').read_text()) if j.get('synthetic',True)]
    for j in jobs:
        j['synthetic']=True;j['source']='Synthetic demo role — not an open vacancy';j['source_url']=''
        j.setdefault('education','');j.setdefault('seniority','junior' if j['min_years']<3 else 'mid')
    seen={(j['title'],j['company']) for j in jobs};n=max(j['id'] for j in jobs)+1
    for page in range(1,5):
        req=urllib.request.Request(f'https://www.arbeitnow.co.uk/api/job-board-api?page={page}',headers={'User-Agent':'Resume2Job educational local snapshot'})
        with urllib.request.urlopen(req,timeout=25) as response:raw=json.load(response)
        for r in raw['data']:
            if (r['title'],r['company_name']) in seen:continue
            j=convert(r,n)
            if j and j['required']:
                jobs.append(j);n+=1;seen.add((j['title'],j['company']))
            if len(jobs)>=180:break
        if len(jobs)>=180:break
    (ROOT/'data/jobs.json').write_text(json.dumps(jobs,indent=2,ensure_ascii=False))
    print(len(jobs),'jobs;',sum(not j['synthetic'] for j in jobs),'real snapshot records')
if __name__=='__main__':main()
