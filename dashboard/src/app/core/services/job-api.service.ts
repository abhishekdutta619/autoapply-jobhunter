import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { Job, JobStatus } from '../models/job.model';

/**
 * REST for state: bulk fetches, historical data, taxonomy updates,
 * and the human-in-the-loop approve/reject actions from the review queue.
 * Not yet backed by a real endpoint - see PROJECT_NOTES.md for the
 * FastAPI service this expects to talk to.
 */
@Injectable({ providedIn: 'root' })
export class JobApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/jobs';

  list(status?: JobStatus): Observable<Job[]> {
    const url = status ? `${this.baseUrl}?status=${status}` : this.baseUrl;
    return this.http.get<Job[]>(url);
  }

  get(id: number): Observable<Job> {
    return this.http.get<Job>(`${this.baseUrl}/${id}`);
  }

  /** Human approves a borderline match - moves it to APPROVED_FOR_APPLY. */
  approve(id: number): Observable<Job> {
    return this.http.patch<Job>(`${this.baseUrl}/${id}/status`, {
      status: JobStatus.ApprovedForApply,
    });
  }

  /** Human rejects a borderline match - moves it to TRASHED. */
  reject(id: number): Observable<Job> {
    return this.http.patch<Job>(`${this.baseUrl}/${id}/status`, {
      status: JobStatus.Trashed,
    });
  }

  /** Manually trigger a Hunter scrape run outside the normal schedule. */
  triggerScrape(source: string): Observable<{ triggered: boolean }> {
    return this.http.post<{ triggered: boolean }>('/api/hunter/trigger', { source });
  }
}
