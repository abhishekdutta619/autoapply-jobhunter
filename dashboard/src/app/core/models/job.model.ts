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
  // The LLM's raw output field is `reasoning` (see RESULT_SCHEMA in
  // app/llm/prompts.py) - evaluate_job() maps it to `job.rationale` on
  // the Job row the moment it's scored, and the API exposes that as
  // `rationale`. This field, not `reasoning`, is what actually reaches
  // the dashboard - don't rename it to match the LLM's raw key.
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