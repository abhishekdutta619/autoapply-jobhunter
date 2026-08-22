import { computed, inject } from '@angular/core';
import { patchState, signalStore, withComputed, withMethods, withState } from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { pipe, switchMap, tap, catchError, of } from 'rxjs';
import { JobApiService } from '../../core/services/job-api.service';
import { Job, JobStatus } from '../../core/models/job.model';

interface PipelineState {
  jobs: Job[];
  loading: boolean;
  error: string | null;
}

const initialState: PipelineState = {
  jobs: [],
  loading: false,
  error: null,
};

/**
 * Fast-moving pipeline metrics need a store that re-renders only the
 * signals that actually changed - a Kanban column shouldn't re-render
 * because a different column's job count changed. SignalStore gives
 * that granularity without NgRx's action/reducer boilerplate, which
 * matters here since state shape (Job[]) is simple but update frequency
 * (live Executor runs) is not.
 */
export const PipelineStore = signalStore(
  { providedIn: 'root' },
  withState(initialState),

  withComputed(({ jobs }) => ({
    byStatus: computed(() => {
      const grouped = new Map<JobStatus, Job[]>();
      for (const status of Object.values(JobStatus)) grouped.set(status, []);
      for (const job of jobs()) grouped.get(job.status)?.push(job);
      return grouped;
    }),
    pendingReviewCount: computed(
      () => jobs().filter((j) => j.status === JobStatus.PendingEvaluation).length,
    ),
  })),

  withMethods((store, api = inject(JobApiService)) => ({
    load: rxMethod<void>(
      pipe(
        tap(() => patchState(store, { loading: true, error: null })),
        switchMap(() =>
          api.list().pipe(
            tap((jobs) => patchState(store, { jobs, loading: false })),
            catchError((err: unknown) => {
              patchState(store, { loading: false, error: 'Failed to load jobs' });
              console.error(err);
              return of(null);
            }),
          ),
        ),
      ),
    ),

    approve(id: number) {
      api.approve(id).subscribe((updated) => {
        patchState(store, {
          jobs: store.jobs().map((j) => (j.id === id ? updated : j)),
        });
      });
    },

    reject(id: number) {
      api.reject(id).subscribe((updated) => {
        patchState(store, {
          jobs: store.jobs().map((j) => (j.id === id ? updated : j)),
        });
      });
    },
  })),
);
