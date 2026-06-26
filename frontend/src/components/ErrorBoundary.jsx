import React from "react";

/**
 * App-level error boundary. Catches uncaught render errors so a stray bug in
 * any sub-tree doesn't blank the whole page. Renders a friendly fallback +
 * a reload button. In production we log to console; can be wired to a
 * monitoring service (Sentry, etc.) later.
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("App ErrorBoundary caught:", error, info && info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div
          className="min-h-screen flex items-center justify-center bg-cream p-6"
          data-testid="error-boundary-fallback"
          role="alert"
        >
          <div className="max-w-md w-full bg-card border-2 border-navy/10 rounded-lg p-6 shadow-md">
            <h1 className="font-serif text-2xl text-navy font-bold mb-2">Something went sideways</h1>
            <p className="text-sm text-navy/80 mb-4">
              The page hit an unexpected error. Try refreshing — if it keeps happening, let us know
              at <a className="text-gold underline" href="mailto:hello@lakeviewburgers.com">hello@lakeviewburgers.com</a>.
            </p>
            {process.env.NODE_ENV !== "production" && this.state.error ? (
              <pre className="text-[10px] font-mono text-red-700 bg-red-50 border border-red-200 rounded p-2 overflow-auto max-h-40 mb-4">
                {String(this.state.error)}
              </pre>
            ) : null}
            <button
              onClick={() => window.location.reload()}
              className="bg-gold text-navy hover:bg-gold/90 px-4 py-2 rounded-sm font-semibold text-sm"
              data-testid="error-boundary-reload"
            >
              Refresh the page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
