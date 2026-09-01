import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { catchError, firstValueFrom, of, tap } from 'rxjs';
import { User } from '../models/user.model';

export type AuthStatus = 'checking' | 'authenticated' | 'anonymous';

/**
 * Talks to app/api/routes/auth.py. There's no login form to submit here -
 * OAuth means the actual credential exchange happens on Google's/GitHub's
 * own pages, entirely outside the Angular app. This service's job is just
 * tracking "are we logged in, and as whom" and kicking off / tearing down
 * that flow via full page navigations to the backend.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);

  readonly status = signal<AuthStatus>('checking');
  readonly user = signal<User | null>(null);

  /** Called once from app.config.ts's app initializer, before the first
   * route activates - the auth guard depends on `status` already being
   * resolved (not 'checking') by the time it runs. */
  async checkSession(): Promise<void> {
    this.status.set('checking');
    await firstValueFrom(
      this.http.get<User>('/api/auth/me').pipe(
        tap((user) => {
          this.user.set(user);
          this.status.set('authenticated');
        }),
        catchError(() => {
          this.user.set(null);
          this.status.set('anonymous');
          return of(null);
        }),
      ),
    );
  }

  /** Full page navigation, not an HttpClient call - this has to leave the
   * SPA entirely so the browser can follow the provider's own redirect
   * chain (consent screen, etc.) and come back with a real session cookie
   * set by the backend's OAuth callback. */
  loginWith(provider: 'google' | 'github'): void {
    window.location.href = `/api/auth/login/${provider}`;
  }

  logout(): void {
    this.http.post('/api/auth/logout', {}).subscribe(() => {
      this.user.set(null);
      this.status.set('anonymous');
      window.location.href = '/login';
    });
  }
}
