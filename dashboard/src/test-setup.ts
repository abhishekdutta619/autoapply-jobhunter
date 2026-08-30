// jsdom (the DOM environment the Vitest-based test runner uses) doesn't
// implement window.matchMedia - it requires real CSS media-query
// evaluation that jsdom doesn't do. ThemeService.resolveInitialTheme()
// calls it to detect the OS's prefers-color-scheme, so any test that
// constructs AppComponent (which injects ThemeService) fails with
// "window.matchMedia is not a function" without this polyfill.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {}, // deprecated, some libraries still check for it
    removeListener: () => {}, // deprecated
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});