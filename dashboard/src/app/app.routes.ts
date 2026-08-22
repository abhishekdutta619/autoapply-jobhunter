import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: 'pipeline', pathMatch: 'full' },
  {
    path: 'pipeline',
    loadComponent: () =>
      import('./features/pipeline/pipeline-container.component').then(
        (m) => m.PipelineContainerComponent,
      ),
  },
  {
    path: 'review',
    loadComponent: () =>
      import('./features/review/review-container.component').then(
        (m) => m.ReviewContainerComponent,
      ),
  },
];
