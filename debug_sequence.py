import time
from app.db.session import get_session
from app.db.models import Job
from app.text_utils import strip_html
from app.llm.ollama_client import OllamaEvaluator
from app.llm.gemini_client import GeminiEvaluator
from app.config import settings

s = get_session()
j = s.get(Job, 223)
resume = open(settings.resume_path).read()

cloud = GeminiEvaluator(api_key=settings.gemini_api_key, model=settings.gemini_model)
local = OllamaEvaluator(base_url=settings.ollama_base_url, model=settings.ollama_model, keep_alive=settings.ollama_keep_alive)

print("Calling cloud first...")
cloud.evaluate_match(resume=resume, job_title=j.title, job_description=strip_html(j.description_html))
print("Cloud done. Calling local immediately after...")

start = time.time()
try:
    result = local.evaluate_match(resume=resume, job_title=j.title, job_description=strip_html(j.description_html))
    print("SUCCESS", time.time() - start, result)
except Exception as exc:
    print("FAILED", time.time() - start, exc)
