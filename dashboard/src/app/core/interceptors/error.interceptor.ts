import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError, timeout, TimeoutError } from 'rxjs';
import { ErrorLogService } from '../services/error-log.service';

const REQUEST_TIMEOUT_MS = 15_000;

/**
 * Catches backend timeouts (the Evaluator/Executor can genuinely hang -
 * see the Workday 422 retry-storm bug in IMPLEMENTATION_GUIDE.md) and
 * surfaces a consistent error shape to every feature, instead of each
 * component handling HttpErrorResponse differently.
 *
 * Also catches a 401 from any *protected* endpoint and bounces to /login -
 * covers a session cookie expiring mid-use, which authGuard alone can't:
 * that only checks once, at initial navigation. /api/auth/me is excluded
 * since a 401 there is AuthService's normal, expected way of finding out
 * nobody's logged in yet, not a session that just expired.
 */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const errorLog = inject(ErrorLogService);
  const router = inject(Router);

  return next(req).pipe(
    timeout(REQUEST_TIMEOUT_MS),
    catchError((err: unknown) => {
      if (err instanceof TimeoutError) {
        errorLog.report(`Request to ${req.url} timed out after ${REQUEST_TIMEOUT_MS}ms`);
      } else if (err instanceof HttpErrorResponse) {
        errorLog.report(`${req.method} ${req.url} failed: ${err.status} ${err.statusText}`);
        if (err.status === 401 && !req.url.includes('/api/auth/me')) {
          router.navigate(['/login']);
        }
      }
      return throwError(() => err);
    }),
  );
};
