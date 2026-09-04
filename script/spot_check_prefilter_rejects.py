from app.db.session import get_session
from app.db.models import Job, JobStatus
from app.text_utils import strip_html

s = get_session()
skipped = (
    s.query(Job)
    .filter(Job.status == JobStatus.TRASHED.value, Job.rationale.like("Pre-filter:%"))
    .order_by(Job.id.desc())
    .limit(10)
    .all()
)
for j in skipped:
    print("=" * 80)
    print(f"id={j.id}  {j.title}")
    print(f"reason: {j.rationale}")
    print("-" * 80)
    print(strip_html(j.description_html or "")[:1500])
