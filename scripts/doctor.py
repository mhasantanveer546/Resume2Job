"""Read-only environment check. Never downloads or chooses a model automatically."""
import sys,platform,shutil,json,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import config,engine,llm
print('Python:',platform.python_version(),' (tested on 3.12)')
print('Jobs:',len(engine.JOBS),'Skills:',len(engine.SK))
print('Ollama executable:',shutil.which('ollama') or 'not installed')
try:
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:11434/api/tags',timeout=2) as r:
        models=json.load(r).get('models',[])
    print('Installed local models:',', '.join(m['name'] for m in models) or 'none')
except Exception:print('Ollama is not running; core workflow will use deterministic fallback.')
print('LLM configured:',llm.configured())
print('Suggested sizing: review available RAM before selecting a model; smaller models use less memory but need more extraction review.')
