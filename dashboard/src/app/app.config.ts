import { ApplicationConfig, inject, provideAppInitializer, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';

import { routes } from './app.routes';
import { errorInterceptor } from './core/interceptors/error.interceptor';
import { AuthService } from './core/services/auth.service';

// No provideZoneChangeDetection here - Angular 21 projects are zoneless
// by default (no zone.js polyfill at all), and everything in this app
// already uses signals + ChangeDetectionStrategy.OnPush, so it fits
// cleanly without opting back into zone-based detection.
export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    // /api and /ws are forwarded to the FastAPI backend on :8000 via
    // proxy.conf.json when running `ng serve` - see dashboard/README
    // (or PROJECT_NOTES.md) for how to run both together.
    provideHttpClient(withInterceptors([errorInterceptor])),
    // Resolves whether we have a valid session before the first route
    // activates, so authGuard never has to guess or race a pending
    // request - it can just read AuthService.status() synchronously.
    provideAppInitializer(() => inject(AuthService).checkSession()),
  ],
};
