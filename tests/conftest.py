import os
os.environ['LLM_BASE_URL']=''
os.environ['LLM_MODEL']=''
import pytest
from app import store
from app.main import app,limits
from fastapi.testclient import TestClient
@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'test.db');limits.clear()
    with TestClient(app) as c:yield c
