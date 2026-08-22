import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';

import { routes } from './app.routes';
import { errorInterceptor } from './core/interceptors/error.interceptor';
import { mockApiInterceptor } from './core/interceptors/mock-api.interceptor';

// No provideZoneChangeDetection here - Angular 21 projects are zoneless
// by default (no zone.js polyfill at all), and everything in this app
// already uses signals + ChangeDetectionStrategy.OnPush, so it fits
// cleanly without opting back into zone-based detection.
export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    // mockApiInterceptor stands in for the FastAPI service that doesn't
    // exist yet - remove it here once real endpoints are live.
    provideHttpClient(withInterceptors([errorInterceptor, mockApiInterceptor])),
  ],
};
