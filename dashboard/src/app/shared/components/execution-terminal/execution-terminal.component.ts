import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { ExecutionLogEntry } from '../../../core/models/job.model';

/**
 * Pure presentational console. Renders whatever log lines it's given -
 * it doesn't know or care whether they came from a WebSocket, a replay
 * of a past run, or a test fixture. That decoupling is the point.
 */
@Component({
  selector: 'app-execution-terminal',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="terminal">
      <div class="terminal__header">
        <span>Executor output</span>
        <button type="button" (click)="killSwitch.emit()" class="terminal__kill">
          Kill switch
        </button>
      </div>
      <div class="terminal__body">
        @for (entry of logs(); track entry.timestamp + entry.message) {
          <div class="terminal__line terminal__line--{{ entry.level }}">
            <span class="terminal__ts">{{ entry.timestamp }}</span>
            {{ entry.message }}
          </div>
        } @empty {
          <div class="terminal__line terminal__line--info">No output yet.</div>
        }
      </div>
    </div>
  `,
  styles: `
    .terminal {
      background: #0b0f19;
      color: #d1d5db;
      border-radius: 8px;
      font-family: 'SFMono-Regular', Consolas, monospace;
      font-size: 13px;
      overflow: hidden;
    }
    .terminal__header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 12px;
      background: #111827;
      color: #9ca3af;
      font-family: system-ui, sans-serif;
      font-size: 12px;
    }
    .terminal__kill {
      background: #7f1d1d;
      color: #fecaca;
      border: none;
      border-radius: 4px;
      padding: 4px 10px;
      font-size: 12px;
      cursor: pointer;
    }
    .terminal__kill:hover { background: #991b1b; }
    .terminal__body {
      max-height: 320px;
      overflow-y: auto;
      padding: 10px 12px;
    }
    .terminal__line { padding: 2px 0; white-space: pre-wrap; }
    .terminal__line--warn  { color: #fbbf24; }
    .terminal__line--error { color: #f87171; }
    .terminal__ts { color: #6b7280; margin-right: 8px; }
  `,
})
export class ExecutionTerminalComponent {
  readonly logs = input.required<ExecutionLogEntry[]>();
  readonly killSwitch = output<void>();
}
