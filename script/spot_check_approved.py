from app.db.session import get_session
from app.db.models import Job, JobStatus

s = get_session()
approved = s.query(Job).filter(Job.status == JobStatus.APPROVED_FOR_APPLY.value).order_by(Job.match_score.desc()).limit(15).all()
for j in approved:
    print(j.id, j.match_score, j.title[:50], "|", (j.rationale or "")[:200])
