import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class ErrorLogService {
  readonly messages = signal<string[]>([]);

  report(message: string): void {
    console.error(message);
    this.messages.update((current) => [...current, message]);
  }
}
