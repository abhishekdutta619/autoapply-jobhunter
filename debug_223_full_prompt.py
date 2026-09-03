import time
from app.db.session import get_session
from app.db.models import Job
from app.text_utils import strip_html
from app.llm.ollama_client import OllamaEvaluator
from app.llm.prompts import build_constraints_section
from app.config import settings

s = get_session()
j = s.get(Job, 223)

resume = open(settings.resume_path).read()
resume += build_constraints_section(
    settings.prefer_remote,
    settings.target_compensation_indian,
    settings.target_compensation_mnc,
)

ev = OllamaEvaluator(base_url=settings.ollama_base_url, model=settings.ollama_model, keep_alive=settings.ollama_keep_alive)
start = time.time()
try:
    result = ev.evaluate_match(resume=resume, job_title=j.title, job_description=strip_html(j.description_html))
    print("SUCCESS", time.time() - start, result)
except Exception as exc:
    print("FAILED", time.time() - start, exc)
