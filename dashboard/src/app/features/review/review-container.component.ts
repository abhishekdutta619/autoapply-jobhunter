import { ChangeDetectionStrategy, Component, computed, inject, OnInit } from '@angular/core';
import { JobStatus } from '../../core/models/job.model';
import { PipelineStore } from '../pipeline/pipeline.store';
import { JobReviewCardComponent } from './job-review-card.component';

/**
 * Smart component: decides "review queue" means jobs with a score but
 * still PENDING_EVALUATION (i.e. Evaluator scored them, but they weren't
 * clear-cut enough to auto-approve/auto-trash). Wires the presentational
 * card's outputs straight to store methods - no logic of its own beyond that.
 */
@Component({
  selector: 'app-review-container',
  standalone: true,
  imports: [JobReviewCardComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="queue">
      <h2 class="queue__heading">
        Review queue
        <span class="queue__count">{{ borderlineJobs().length }}</span>
      </h2>

      @for (job of borderlineJobs(); track job.id) {
        <app-job-review-card
          [job]="job"
          (approve)="store.approve($event)"
          (reject)="store.reject($event)"
        />
      } @empty {
        <p class="queue__empty">Nothing waiting on a manual decision right now.</p>
      }
    </div>
  `,
  styles: `
    .queue { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
    .queue__heading {
      font-size: 16px;
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .queue__count {
      font-size: 12px;
      background: #e5e7eb;
      color: #374151;
      border-radius: 999px;
      padding: 1px 8px;
    }
    .queue__empty { font-size: 13px; color: #9ca3af; }
  `,
})
export class ReviewContainerComponent implements OnInit {
  protected readonly store = inject(PipelineStore);

  protected readonly borderlineJobs = computed(() =>
    this.store.jobs().filter((j) => j.status === JobStatus.PendingEvaluation && j.matchScore !== null),
  );

  ngOnInit(): void {
    this.store.load();
  }
}
