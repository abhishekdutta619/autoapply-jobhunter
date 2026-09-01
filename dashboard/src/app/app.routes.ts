import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  { path: '', redirectTo: 'pipeline', pathMatch: 'full' },
  {
    path: 'login',
    loadComponent: () => import('./features/auth/login.component').then((m) => m.LoginComponent),
  },
  {
    path: 'pipeline',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/pipeline/pipeline-container.component').then(
        (m) => m.PipelineContainerComponent,
      ),
  },
  {
    path: 'review',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/review/review-container.component').then(
        (m) => m.ReviewContainerComponent,
      ),
  },
];
