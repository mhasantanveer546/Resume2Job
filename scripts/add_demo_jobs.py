import json,pathlib
f=pathlib.Path(__file__).resolve().parents[1]/'data/jobs.json'
jobs=json.loads(f.read_text(encoding='utf-8'))
S='Synthetic demo role — not an open vacancy'
def J(i,t,c,loc,mode,typ,yrs,req,pre,desc,sen='junior'):
    return dict(id=i,title=t,company=c,location=loc,mode=mode,type=typ,min_years=yrs,required=req,preferred=pre,description=desc,source=S,synthetic=True,source_url='',education="Bachelor's degree in Computer Science or equivalent",seniority=sen)
new=[
 J(1001,'Junior Python Backend Developer (Flask/FastAPI)','Lahore Labs','Lahore, Pakistan','hybrid','full-time',0,['Python','Flask','SQL','Git','Docker'],['REST APIs','FastAPI','PostgreSQL','Unit Testing','CI/CD'],'Build and maintain REST APIs in Python with Flask and FastAPI. Write SQL queries, use Git daily, containerize services with Docker, and add unit testing and CI/CD pipelines.'),
 J(1002,'Backend Engineering Intern (Python)','Karachi Tech','Karachi, Pakistan','remote','internship',0,['Python','SQL','Git','REST APIs'],['Docker','Flask'],'Internship building REST API endpoints in Python with SQL databases under senior guidance.','entry'),
 J(1003,'Junior Full-Stack Developer (Python/JS)','Pixel Foundry','Lahore, Pakistan','on-site','full-time',1,['Python','JavaScript','HTML','CSS','SQL','Git'],['Flask','Docker'],'Develop full-stack features with Python backends and JavaScript frontends.'),
]
ids={j['id'] for j in jobs}
jobs+=[j for j in new if j['id'] not in ids]
f.write_text(json.dumps(jobs,indent=2,ensure_ascii=False),encoding='utf-8')
print(len(jobs),'jobs')