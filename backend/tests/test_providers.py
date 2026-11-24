import pytest
import httpx
from sqlalchemy import select, text
from app.providers import CompatibleChatProvider, CompatibleEmbeddingProvider, ProviderError, configured, request_json
from app.config import Settings
from app.research import validate_citations
from app.models import Paper, Chunk

def test_compatible_chat_and_embedding_wire_contract(monkeypatch):
    requests=[]
    real=httpx.Client
    def handle(request):
        import json
        body=json.loads(request.content)
        requests.append((str(request.url),body,request.headers.get("authorization")))
        if request.url.path.endswith("chat/completions"):
            return httpx.Response(200,json={"choices":[{"message":{"content":'{"claims":[]}'}}]})
        return httpx.Response(200,json={"data":[{"index":1,"embedding":[0,1]},{"index":0,"embedding":[1,0]}]})
    monkeypatch.setattr(httpx,"Client",lambda **kwargs:real(transport=httpx.MockTransport(handle),**kwargs))
    settings=Settings(_env_file=None,ai_chat_model="test-model",ai_api_key="test-secret",embedding_model="embed-model",embedding_api_key="separate-secret")
    assert CompatibleChatProvider(settings).generate("rules",{"question":"hi"})=={"claims":[]}
    assert CompatibleEmbeddingProvider(settings).embed(["a","b"])==[[1.0,0.0],[0.0,1.0]]
    assert requests[0][1]["model"]=="test-model"
    assert requests[0][1]["max_completion_tokens"]==1800
    assert requests[0][2]=="Bearer test-secret"
    assert requests[1][2]=="Bearer separate-secret"
    assert "tools" not in requests[0][1]

def test_provider_errors_sanitized_and_finite_retries(monkeypatch):
    calls=[]
    real=httpx.Client
    def handle(request):
        calls.append(request)
        return httpx.Response(429,text="sensitive response including some secret")
    monkeypatch.setattr(httpx,"Client",lambda **kwargs:real(transport=httpx.MockTransport(handle),**kwargs))
    settings=Settings(_env_file=None,ai_retries=1)
    with pytest.raises(ProviderError,match="HTTP 429") as error:
        request_json("https://example.com/v1","secret","chat/completions",{},settings)
    assert len(calls)==2 and "sensitive" not in str(error.value)

def test_nonfinite_vectors_and_nonobject_chat_rejected(monkeypatch):
    real=httpx.Client
    mode=["vectors"]
    def handle(request):
        if mode[0]=="vectors": return httpx.Response(200,json={"data":[{"index":0,"embedding":[0,0]}]})
        return httpx.Response(200,json={"choices":[{"message":{"content":"[]"}}]})
    monkeypatch.setattr(httpx,"Client",lambda **kwargs:real(transport=httpx.MockTransport(handle),**kwargs))
    s=Settings(_env_file=None)
    with pytest.raises(ProviderError): CompatibleEmbeddingProvider(s).embed(["a"])
    mode[0]="chat"
    with pytest.raises(ProviderError): CompatibleChatProvider(s).generate("rules",{})

def test_reference_quote_page_and_bool_validation():
    source={"paper_id":"paper","chunk_id":"chunk","page_number":1,"quote":"This is original evidence.","title":"Test"}
    assert validate_citations([{**source,"quote":"original evidence"}],[source])
    assert not validate_citations([{**source,"page_number":True}],[source])
    assert not validate_citations([{**source,"page_number":2}],[source])
    assert not validate_citations([{**source,"quote":"fabricated evidence"}],[source])
    assert not validate_citations([{**source,"paper_id":"other-project"}],[source])

def test_provider_local_configuration():
    assert configured("http://127.0.0.1:11434/v1","local","")
    assert not configured("https://api.openai.com/v1","remote","")
    assert not configured("http://example.org/v1","remote","")
