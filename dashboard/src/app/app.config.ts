import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';

import { routes } from './app.routes';
import { errorInterceptor } from './core/interceptors/error.interceptor';

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
  ],
};
