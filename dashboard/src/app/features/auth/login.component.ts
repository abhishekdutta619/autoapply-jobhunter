import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

const ERROR_MESSAGES: Record<string, string> = {
  oauth_failed: "That didn't go through - the sign-in was cancelled or expired. Try again.",
  no_email: "Your account didn't share an email address, so there's nothing to sign in with.",
};

@Component({
  selector: 'app-login',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="login">
      <section class="login__panel login__panel--form">
        <div class="login__form-inner">
          <h1 class="login__heading">Welcome back</h1>
          <p class="login__subheading">Sign in to manage your job pipeline</p>

          <button type="button" class="login__oauth-btn" (click)="auth.loginWith('google')">
            <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
              <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 6.5 29.6 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.5z" />
              <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.6 15.1 18.9 12 24 12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 6.5 29.6 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
              <path fill="#4CAF50" d="M24 44c5.5 0 10.4-1.9 14.3-5.1l-6.6-5.6C29.6 35.4 26.9 36 24 36c-5.3 0-9.7-3.3-11.3-8l-6.6 5.1C9.6 39.7 16.2 44 24 44z" />
              <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.3 4.3-4.2 5.7l6.6 5.6C39.9 37.6 44 31.9 44 24c0-1.3-.1-2.7-.4-3.5z" />
            </svg>
            Continue with Google
          </button>

          <button type="button" class="login__oauth-btn" (click)="auth.loginWith('github')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 .5C5.73.5.98 5.24.98 11.5c0 4.84 3.13 8.94 7.47 10.39.55.1.75-.24.75-.53 0-.26-.01-1.13-.02-2.04-3.04.66-3.68-1.3-3.68-1.3-.5-1.26-1.22-1.6-1.22-1.6-.99-.68.08-.67.08-.67 1.1.08 1.68 1.13 1.68 1.13.98 1.68 2.57 1.2 3.2.92.1-.71.38-1.2.7-1.48-2.43-.28-4.98-1.21-4.98-5.4 0-1.19.42-2.17 1.12-2.93-.11-.28-.49-1.4.11-2.92 0 0 .92-.29 3 1.12a10.4 10.4 0 0 1 5.46 0c2.08-1.41 3-1.12 3-1.12.6 1.52.22 2.64.11 2.92.7.76 1.12 1.74 1.12 2.93 0 4.2-2.56 5.12-5 5.39.39.34.73 1.01.73 2.04 0 1.47-.01 2.66-.01 3.02 0 .29.2.64.76.53 4.34-1.45 7.47-5.55 7.47-10.39C23.02 5.24 18.27.5 12 .5Z" />
            </svg>
            Continue with GitHub
          </button>

          @if (errorMessage()) {
            <p class="login__error">{{ errorMessage() }}</p>
          }

          <p class="login__note">
            Signing in creates your account automatically - there's no separate sign-up step.
          </p>
        </div>
      </section>

      <section class="login__panel login__panel--brand">
        <div class="login__brand-inner">
          <h2 class="login__brand-heading">Automate your job search pipeline</h2>
          <p class="login__brand-sub">
            Scrapes postings across ATS platforms, scores them against your resume, and only
            asks for your input on the borderline calls.
          </p>
          <div class="login__preview">
            <span class="login__preview-col" style="background: var(--col-pending)"></span>
            <span class="login__preview-col" style="background: var(--col-approved)"></span>
            <span class="login__preview-col" style="background: var(--col-applying)"></span>
            <span class="login__preview-col" style="background: var(--col-applied)"></span>
          </div>
          <p class="login__preview-caption">Pending &rarr; Approved &rarr; Applying &rarr; Applied</p>
        </div>
      </section>
    </div>
  `,
  styles: `
    .login {
      display: flex;
      min-height: calc(100vh - 56px);
    }
    .login__panel {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 40px;
    }
    .login__panel--form {
      background: var(--bg-surface);
    }
    .login__form-inner {
      width: 100%;
      max-width: 340px;
    }
    .login__heading {
      font-size: 26px;
      font-weight: 700;
      margin: 0;
      color: var(--text-primary);
    }
    .login__subheading {
      font-size: 14px;
      color: var(--text-secondary);
      margin: 6px 0 28px;
    }
    .login__oauth-btn {
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      padding: 11px 0;
      margin-bottom: 12px;
      border-radius: 8px;
      border: 1px solid var(--border-strong);
      background: var(--bg-surface);
      color: var(--text-primary);
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
    }
    .login__oauth-btn:hover {
      background: var(--bg-column);
    }
    .login__error {
      font-size: 13px;
      color: var(--text-danger);
      background: var(--bg-danger);
      border-radius: 6px;
      padding: 8px 12px;
      margin-top: 8px;
    }
    .login__note {
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 20px;
      line-height: 1.5;
    }
    .login__panel--brand {
      background: linear-gradient(135deg, var(--col-pending), var(--col-approved));
      color: white;
    }
    .login__brand-inner {
      max-width: 380px;
    }
    .login__brand-heading {
      font-size: 26px;
      font-weight: 700;
      margin: 0 0 12px;
      line-height: 1.25;
    }
    .login__brand-sub {
      font-size: 14px;
      line-height: 1.6;
      opacity: 0.92;
      margin: 0 0 28px;
    }
    .login__preview {
      display: flex;
      gap: 6px;
      height: 8px;
      border-radius: 999px;
      overflow: hidden;
    }
    .login__preview-col {
      flex: 1;
    }
    .login__preview-caption {
      font-size: 12px;
      opacity: 0.85;
      margin-top: 10px;
    }
    @media (max-width: 720px) {
      .login {
        flex-direction: column;
      }
      .login__panel--brand {
        order: -1;
        padding: 28px 40px;
      }
      .login__brand-sub {
        display: none;
      }
    }
  `,
})
export class LoginComponent {
  protected readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);

  private readonly errorParam = toSignal(this.route.queryParamMap, { initialValue: null });

  protected readonly errorMessage = computed(() => {
    const code = this.errorParam()?.get('error');
    return code ? (ERROR_MESSAGES[code] ?? 'Something went wrong signing you in.') : null;
  });
}
