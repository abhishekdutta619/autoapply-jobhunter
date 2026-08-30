import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { Job } from '../../core/models/job.model';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';

/**
 * Strictly presentational. It renders the job and the LLM's rationale
 * and emits intent (approve/reject) - it never calls the API directly.
 * That keeps it trivially testable and reusable (e.g. in a future
 * "review history" read-only view, just by not listening to the outputs).
 */
@Component({
  selector: 'app-job-review-card',
  standalone: true,
  imports: [StatusBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <article class="card">
      <header class="card__header">
        <div>
          <h3 class="card__title">{{ job().title }}</h3>
          <p class="card__company">{{ job().company }} · {{ job().location ?? 'Remote/unspecified' }}</p>
        </div>
        <app-status-badge [status]="job().status" />
      </header>

      @if (job().matchScore !== null) {
        <div class="card__score">Match score: {{ job().matchScore }}/100</div>
      }

      @if (job().rationale) {
        <p class="card__rationale">{{ job().rationale }}</p>
      } @else {
        <p class="card__rationale card__rationale--empty">
          No rationale available for this job yet.
        </p>
      }

      <div class="card__actions">
        <button type="button" class="card__btn card__btn--reject" (click)="reject.emit(job().id)">
          Reject
        </button>
        <button type="button" class="card__btn card__btn--approve" (click)="approve.emit(job().id)">
          Approve
        </button>
      </div>
    </article>
  `,
  styles: `
    .card {
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px;
      max-width: 420px;
    }
    .card__header { display: flex; justify-content: space-between; gap: 8px; }
    .card__title { font-size: 15px; font-weight: 500; margin: 0; color: var(--text-primary); }
    .card__company { font-size: 13px; color: var(--text-secondary); margin: 2px 0 0; }
    .card__score { font-size: 13px; color: var(--text-primary); margin: 10px 0 4px; }
    .card__rationale { font-size: 13px; color: var(--text-secondary); line-height: 1.5; }
    .card__rationale--empty { color: var(--text-muted); font-style: italic; }
    .card__actions { display: flex; gap: 8px; margin-top: 12px; }
    .card__btn {
      flex: 1;
      padding: 8px 0;
      border-radius: 6px;
      border: none;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
    }
    .card__btn--approve { background: var(--text-success); color: white; }
    .card__btn--approve:hover { opacity: 0.85; }
    .card__btn--reject { background: var(--bg-neutral); color: var(--text-neutral); }
    .card__btn--reject:hover { background: var(--border-strong); }
  `,
})
export class JobReviewCardComponent {
  readonly job = input.required<Job>();
  readonly approve = output<number>();
  readonly reject = output<number>();
}
