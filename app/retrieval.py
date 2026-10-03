"""Local retrieval: cached TF-IDF index, optional locally installed embeddings.
No downloads happen during a request. Retrieved resource IDs ground advisor output.
"""
import json, os, hashlib
from functools import lru_cache
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .config import ROOT
@lru_cache(maxsize=4)
def _index(documents):
    vectorizer=TfidfVectorizer(stop_words='english',ngram_range=(1,2),sublinear_tf=True)
    return vectorizer,vectorizer.fit_transform(documents)
@lru_cache(maxsize=1)
def _model(path):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(path,local_files_only=True,device='cpu')
@lru_cache(maxsize=4)
def _vectors(path,documents):return _model(path).encode(list(documents),normalize_embeddings=True)
def job_similarities(text,jobs):
    docs=tuple(j['title']+' '+j['description']+' '+' '.join(j['required']) for j in jobs)
    path=os.getenv('EMBEDDING_MODEL_PATH','')
    if path:
        try:
            q=_model(path).encode([text],normalize_embeddings=True)
            return np.maximum(0,(_vectors(path,docs)@q.T).ravel()),'local embeddings'
        except Exception: pass  # Optional engine failure is disclosed by the returned mode.
    try:
        v,m=_index(docs);return cosine_similarity(v.transform([text]),m).ravel(),'TF-IDF fallback'
    except ValueError:return np.zeros(len(jobs)),'TF-IDF (empty vocabulary)'
RESOURCES=json.loads((ROOT/'data/learning_resources.json').read_text(encoding='utf-8'))
def lookup_learning_resources(skills,limit=5):
    """Retrieve only resources tagged with an actual candidate gap, then rank chunks."""
    pool=[r for r in RESOURCES if set(r['skills'])&set(skills)]
    if not pool:return []
    docs=tuple(r['title']+' '+r['content']+' '+' '.join(r['skills']) for r in pool)
    v,m=_index(docs);scores=cosine_similarity(v.transform([' '.join(skills)]),m).ravel()
    return [{**pool[i],'retrieval_score':round(float(scores[i]),3)} for i in np.argsort(-scores)[:limit]]
