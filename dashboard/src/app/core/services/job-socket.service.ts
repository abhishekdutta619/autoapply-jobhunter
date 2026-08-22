import { Injectable, signal } from '@angular/core';
import { ExecutionLogEntry } from '../models/job.model';

/**
 * WebSockets for action: reserved for the Executor phase only, per the
 * backend integration strategy. REST covers everything else. This gives
 * you a live feed while the browser bot is navigating a real ATS form,
 * plus a kill switch if it gets stuck on something like the Workday
 * /job/job/ bug class of issue.
 *
 * Not yet backed by a real endpoint - the FastAPI service needs a
 * `/ws/executor/{job_id}` route that forwards runner.py's progress
 * events. Connect() is a no-op stub until that exists.
 */
@Injectable({ providedIn: 'root' })
export class JobSocketService {
  private socket: WebSocket | null = null;

  readonly logs = signal<ExecutionLogEntry[]>([]);
  readonly connected = signal(false);

  connect(jobId: number): void {
    this.disconnect();

    const wsUrl = `${location.origin.replace(/^http/, 'ws')}/ws/executor/${jobId}`;
    this.socket = new WebSocket(wsUrl);

    this.socket.onopen = () => this.connected.set(true);
    this.socket.onclose = () => this.connected.set(false);
    this.socket.onerror = () => this.connected.set(false);

    this.socket.onmessage = (event: MessageEvent<string>) => {
      const entry: ExecutionLogEntry = JSON.parse(event.data);
      this.logs.update((current) => [...current, entry]);
    };
  }

  /** Kill switch: tells the backend to abandon the in-progress Executor run. */
  killSwitch(jobId: number): void {
    this.socket?.send(JSON.stringify({ action: 'kill', jobId }));
  }

  disconnect(): void {
    this.socket?.close();
    this.socket = null;
    this.connected.set(false);
    this.logs.set([]);
  }
}
