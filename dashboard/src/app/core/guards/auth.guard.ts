import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

/**
 * By the time any guard runs, app.config.ts's app initializer has already
 * awaited AuthService.checkSession() once, so `status` here is always
 * 'authenticated' or 'anonymous' - never 'checking'. No need to subscribe
 * to changes; a stale allow after logout is prevented by AuthService.logout()
 * doing a full page reload, which re-runs the initializer from scratch.
 */
export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  return auth.status() === 'authenticated' ? true : router.createUrlTree(['/login']);
};
