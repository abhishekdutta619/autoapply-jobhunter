import { ChangeDetectionStrategy, Component, inject, OnInit } from '@angular/core';
import { JobStatus } from '../../core/models/job.model';
import { PipelineStore } from './pipeline.store';

const COLUMN_ORDER: JobStatus[] = [
  JobStatus.PendingEvaluation,
  JobStatus.ApprovedForApply,
  JobStatus.Applying,
  JobStatus.Applied,
  JobStatus.Failed,
  JobStatus.Trashed,
];

const COLUMN_LABELS: Record<JobStatus, string> = {
  [JobStatus.PendingEvaluation]: 'Pending evaluation',
  [JobStatus.ApprovedForApply]: 'Approved',
  [JobStatus.Applying]: 'Applying',
  [JobStatus.Applied]: 'Applied',
  [JobStatus.Failed]: 'Failed',
  [JobStatus.Trashed]: 'Trashed',
};

// CSS custom property per column, set on styles.scss (light + dark variants).
const COLUMN_COLOR_VAR: Record<JobStatus, string> = {
  [JobStatus.PendingEvaluation]: '--col-pending',
  [JobStatus.ApprovedForApply]: '--col-approved',
  [JobStatus.Applying]: '--col-applying',
  [JobStatus.Applied]: '--col-applied',
  [JobStatus.Failed]: '--col-failed',
  [JobStatus.Trashed]: '--col-trashed',
};

function scoreBand(score: number | null): 'high' | 'mid' | 'low' | 'none' {
  if (score === null) return 'none';
  if (score >= 80) return 'high';
  if (score >= 50) return 'mid';
  return 'low';
}

/**
 * Smart component: owns the store injection, decides which columns to
 * render and in what order. It does not know how a job card renders in
 * detail - it just maps a status to a label/color and a score to a band.
 */
@Component({
  selector: 'app-pipeline-container',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="board">
      @for (status of columnOrder; track status) {
        <section class="board__column">
          <header class="board__column-header" [style.background]="'var(' + colorVar(status) + ')'">
            <h3>{{ label(status) }}</h3>
            <span class="board__count">{{ (store.byStatus().get(status) ?? []).length }}</span>
          </header>

          <div class="board__column-body">
            @for (job of store.byStatus().get(status) ?? []; track job.id) {
              <a class="board__card" [href]="job.applyUrl" target="_blank" rel="noopener noreferrer">
                <div class="board__card-top">
                  <div class="board__card-title">{{ job.title }}</div>
                  <svg class="board__card-link-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                    <path d="M15 3h6v6M10 14 21 3" />
                  </svg>
                </div>
                <div class="board__card-company">{{ job.company }}@if (job.location) { &middot; {{ job.location }} }</div>
                @if (job.matchScore !== null) {
                  <span class="board__card-score" [class]="'board__card-score--' + scoreBand(job.matchScore)">
                    {{ job.matchScore }} match
                  </span>
                }
              </a>
            } @empty {
              <p class="board__empty">No jobs in this stage.</p>
            }
          </div>
        </section>
      }
    </div>
  `,
  styles: `
    .board {
      display: grid;
      grid-auto-flow: column;
      grid-auto-columns: minmax(220px, 1fr);
      gap: 16px;
      overflow-x: auto;
      padding: 16px;
    }
    .board__column {
      background: var(--bg-column);
      border-radius: 10px;
      overflow: hidden;
      min-height: 200px;
      display: flex;
      flex-direction: column;
    }
    .board__column-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      padding: 10px 12px;
    }
    .board__column-header h3 {
      font-size: 13px;
      font-weight: 600;
      color: white;
      margin: 0;
    }
    .board__column-body {
      padding: 12px;
      flex: 1;
    }
    .board__count {
      font-size: 12px;
      color: white;
      background: rgba(255, 255, 255, 0.25);
      border-radius: 999px;
      padding: 1px 8px;
    }
    .board__card {
      display: block;
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px;
      margin-bottom: 8px;
      text-decoration: none;
      color: inherit;
    }
    .board__card:hover {
      border-color: var(--border-strong);
    }
    .board__card-top {
      display: flex;
      justify-content: space-between;
      align-items: start;
      gap: 6px;
    }
    .board__card-link-icon {
      flex-shrink: 0;
      margin-top: 2px;
      color: var(--text-muted);
    }
    .board__card-title { font-size: 13px; font-weight: 500; color: var(--text-primary); }
    .board__card-company { font-size: 12px; color: var(--text-secondary); margin: 2px 0 6px; }
    .board__card-score {
      display: inline-block;
      font-size: 11px;
      font-weight: 500;
      padding: 2px 8px;
      border-radius: 999px;
    }
    .board__card-score--high { background: var(--bg-success); color: var(--text-success); }
    .board__card-score--mid  { background: var(--bg-warning); color: var(--text-warning); }
    .board__card-score--low  { background: var(--bg-danger); color: var(--text-danger); }
    .board__card-score--none { background: var(--bg-neutral); color: var(--text-neutral); }
    .board__empty { font-size: 12px; color: var(--text-muted); }
  `,
})
export class PipelineContainerComponent implements OnInit {
  protected readonly store = inject(PipelineStore);
  protected readonly columnOrder = COLUMN_ORDER;

  protected label(status: JobStatus): string {
    return COLUMN_LABELS[status];
  }

  protected colorVar(status: JobStatus): string {
    return COLUMN_COLOR_VAR[status];
  }

  protected scoreBand = scoreBand;

  ngOnInit(): void {
    this.store.load();
  }
}
