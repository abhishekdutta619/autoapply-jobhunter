from app.db.session import get_session
from app.db.models import Job, JobStatus

s = get_session()
candidates = (
    s.query(Job)
    .filter(Job.status == JobStatus.TRASHED.value, Job.match_score >= 60, Job.match_score < 85)
    .order_by(Job.match_score.desc())
    .limit(10)
    .all()
)
for j in candidates:
    print(j.id, j.match_score, j.title[:60], "|", j.apply_url)
