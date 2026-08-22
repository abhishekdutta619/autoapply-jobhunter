// Mirrors app/db/models.py's Job / JobStatus in the Python backend.
// Field names and the status enum are kept identical to the DB columns
// so the API layer can be a thin serialization pass, not a translation layer.

export enum JobStatus {
  PendingEvaluation = 'PENDING_EVALUATION',
  ApprovedForApply = 'APPROVED_FOR_APPLY',
  Trashed = 'TRASHED',
  Applying = 'APPLYING',
  Applied = 'APPLIED',
  Failed = 'FAILED',
}

export interface Job {
  id: number;
  source: string;
  externalId: string;
  title: string;
  company: string;
  location: string | null;
  applyUrl: string;
  postedAt: string | null; // ISO 8601
  status: JobStatus;
  matchScore: number | null;
  /**
   * TODO(backend): app/llm/base.py's EvaluationResult already produces a
   * `reasoning: str`, but app/evaluator.py currently only persists
   * `match_score` onto the Job row - the rationale text itself isn't
   * stored anywhere yet. The review card below needs this to be useful.
   * Either add a `rationale` column to the jobs table, or a side table
   * keyed by job_id, before the API layer can return real values here.
   */
  rationale: string | null;
  scrapedAt: string;
  updatedAt: string;
}

/** One line of live Executor telemetry, streamed over WebSocket/SSE. */
export interface ExecutionLogEntry {
  jobId: number;
  timestamp: string;
  level: 'info' | 'warn' | 'error';
  message: string;
}
