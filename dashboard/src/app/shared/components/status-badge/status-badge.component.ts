import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { JobStatus } from '../../../core/models/job.model';

const STATUS_LABELS: Record<JobStatus, string> = {
  [JobStatus.PendingEvaluation]: 'Pending evaluation',
  [JobStatus.ApprovedForApply]: 'Approved',
  [JobStatus.Trashed]: 'Trashed',
  [JobStatus.Applying]: 'Applying',
  [JobStatus.Applied]: 'Applied',
  [JobStatus.Failed]: 'Failed',
};

const STATUS_CLASSES: Record<JobStatus, string> = {
  [JobStatus.PendingEvaluation]: 'badge--neutral',
  [JobStatus.ApprovedForApply]: 'badge--success',
  [JobStatus.Trashed]: 'badge--muted',
  [JobStatus.Applying]: 'badge--info',
  [JobStatus.Applied]: 'badge--success',
  [JobStatus.Failed]: 'badge--danger',
};

@Component({
  selector: 'app-status-badge',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span class="badge {{ cssClass() }}">{{ label() }}</span>`,
  styles: `
    .badge {
      display: inline-block;
      padding: 2px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 500;
    }
    .badge--neutral { background: var(--bg-neutral); color: var(--text-neutral); }
    .badge--success { background: var(--bg-success); color: var(--text-success); }
    .badge--muted   { background: var(--bg-muted); color: var(--text-mutedbadge); }
    .badge--info    { background: var(--bg-info); color: var(--text-info); }
    .badge--danger  { background: var(--bg-danger); color: var(--text-danger); }
  `,
})
export class StatusBadgeComponent {
  readonly status = input.required<JobStatus>();

  protected readonly label = computed(() => STATUS_LABELS[this.status()]);
  protected readonly cssClass = computed(() => STATUS_CLASSES[this.status()]);
}
