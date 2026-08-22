import { HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { delay, of } from 'rxjs';
import { Job, JobStatus } from '../models/job.model';

// Fixture data standing in for the ~1,556 real jobs sitting in SQLite,
// covering every JobStatus so every Kanban column and the review queue
// have something to render. Delete this whole interceptor once
// GET/PATCH /api/jobs is real.
const MOCK_JOBS: Job[] = [
  {
    id: 1, source: 'greenhouse', externalId: 'gh-101',
    title: 'Senior Frontend Engineer', company: 'Doordash',
    location: 'Bengaluru, IN', applyUrl: 'https://example.com/apply/1',
    postedAt: '2026-08-15T00:00:00Z', status: JobStatus.PendingEvaluation,
    matchScore: 78,
    rationale: 'Strong Angular/TypeScript overlap with candidate profile; salary band unconfirmed.',
    scrapedAt: '2026-08-16T00:00:00Z', updatedAt: '2026-08-16T00:00:00Z',
  },
  {
    id: 2, source: 'lever', externalId: 'lv-202',
    title: 'Staff Software Engineer, Platform', company: 'Notion',
    location: 'Remote', applyUrl: 'https://example.com/apply/2',
    postedAt: '2026-08-14T00:00:00Z', status: JobStatus.ApprovedForApply,
    matchScore: 92, rationale: 'High seniority and remote match; strong signal on required skills.',
    scrapedAt: '2026-08-16T00:00:00Z', updatedAt: '2026-08-16T00:00:00Z',
  },
  {
    id: 3, source: 'ashby', externalId: 'ash-303',
    title: 'Frontend Engineer, Growth', company: 'Ramp',
    location: 'Remote', applyUrl: 'https://example.com/apply/3',
    postedAt: '2026-08-13T00:00:00Z', status: JobStatus.Applying,
    matchScore: 85, rationale: null,
    scrapedAt: '2026-08-15T00:00:00Z', updatedAt: '2026-08-16T00:00:00Z',
  },
  {
    id: 4, source: 'workday', externalId: 'wd-404',
    title: 'UI Engineer', company: 'NVIDIA',
    location: 'Pune, IN', applyUrl: 'https://example.com/apply/4',
    postedAt: '2026-08-10T00:00:00Z', status: JobStatus.Applied,
    matchScore: 81, rationale: null,
    scrapedAt: '2026-08-11T00:00:00Z', updatedAt: '2026-08-15T00:00:00Z',
  },
  {
    id: 5, source: 'greenhouse', externalId: 'gh-505',
    title: 'Backend Engineer, Payments', company: 'Doordash',
    location: 'Bengaluru, IN', applyUrl: 'https://example.com/apply/5',
    postedAt: '2026-08-09T00:00:00Z', status: JobStatus.Failed,
    matchScore: 40, rationale: null,
    scrapedAt: '2026-08-10T00:00:00Z', updatedAt: '2026-08-12T00:00:00Z',
  },
  {
    id: 6, source: 'lever', externalId: 'lv-606',
    title: 'Data Engineer', company: 'Generic Co',
    location: 'Hyderabad, IN', applyUrl: 'https://example.com/apply/6',
    postedAt: '2026-08-08T00:00:00Z', status: JobStatus.Trashed,
    matchScore: 22,
    rationale: 'Role requires 8+ years data engineering; profile is frontend-focused.',
    scrapedAt: '2026-08-09T00:00:00Z', updatedAt: '2026-08-10T00:00:00Z',
  },
];

export const mockApiInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.url === '/api/jobs' && req.method === 'GET') {
    return of(new HttpResponse({ status: 200, body: MOCK_JOBS })).pipe(delay(200));
  }

  const patchMatch = req.url.match(/^\/api\/jobs\/(\d+)\/status$/);
  if (patchMatch && req.method === 'PATCH') {
    const id = Number(patchMatch[1]);
    const job = MOCK_JOBS.find((j) => j.id === id);
    if (job) job.status = (req.body as { status: JobStatus }).status;
    return of(new HttpResponse({ status: 200, body: job })).pipe(delay(150));
  }

  return next(req);
};
