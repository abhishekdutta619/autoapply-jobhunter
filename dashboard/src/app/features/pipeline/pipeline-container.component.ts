import { ChangeDetectionStrategy, Component, inject, OnInit } from '@angular/core';
import { JobStatus } from '../../core/models/job.model';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';
import { PipelineStore } from './pipeline.store';

const COLUMN_ORDER: JobStatus[] = [
  JobStatus.PendingEvaluation,
  JobStatus.ApprovedForApply,
  JobStatus.Applying,
  JobStatus.Applied,
  JobStatus.Failed,
  JobStatus.Trashed,
];

/**
 * Smart component: owns the store injection, decides which columns to
 * render and in what order. It does not know how a job card renders -
 * that's shared/StatusBadge's job. Kept dumb-component-free of business
 * logic like scoring or status transitions; those live in the store.
 */
@Component({
  selector: 'app-pipeline-container',
  standalone: true,
  imports: [StatusBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="board">
      @for (status of columnOrder; track status) {
        <section class="board__column">
          <header class="board__column-header">
            <h3>{{ status }}</h3>
            <span class="board__count">{{ (store.byStatus().get(status) ?? []).length }}</span>
          </header>

          @for (job of store.byStatus().get(status) ?? []; track job.id) {
            <article class="board__card">
              <div class="board__card-title">{{ job.title }}</div>
              <div class="board__card-company">{{ job.company }}</div>
              @if (job.matchScore !== null) {
                <div class="board__card-score">Score: {{ job.matchScore }}</div>
              }
              <app-status-badge [status]="job.status" />
            </article>
          } @empty {
            <p class="board__empty">No jobs in this stage.</p>
          }
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
      background: #f9fafb;
      border-radius: 10px;
      padding: 12px;
      min-height: 200px;
    }
    .board__column-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 10px;
    }
    .board__column-header h3 {
      font-size: 13px;
      font-weight: 500;
      color: #374151;
      text-transform: capitalize;
    }
    .board__count {
      font-size: 12px;
      color: #6b7280;
      background: #e5e7eb;
      border-radius: 999px;
      padding: 1px 8px;
    }
    .board__card {
      background: white;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 10px;
      margin-bottom: 8px;
    }
    .board__card-title { font-size: 13px; font-weight: 500; }
    .board__card-company { font-size: 12px; color: #6b7280; margin: 2px 0 6px; }
    .board__card-score { font-size: 12px; color: #4b5563; margin-bottom: 6px; }
    .board__empty { font-size: 12px; color: #9ca3af; }
  `,
})
export class PipelineContainerComponent implements OnInit {
  protected readonly store = inject(PipelineStore);
  protected readonly columnOrder = COLUMN_ORDER;

  ngOnInit(): void {
    this.store.load();
  }
}
