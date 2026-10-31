import { Component, type ReactNode } from "react";
import { AlertCircle } from "lucide-react";

export class ConsoleBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <div className="error-state" role="alert">
          <AlertCircle size={30} />
          <h2>The console could not display this response</h2>
          <p>
            No results have been substituted. Reload the console and check that
            the backend contract matches this version.
          </p>
          <button
            className="button primary"
            onClick={() => window.location.reload()}
          >
            Reload console
          </button>
        </div>
      );
    return this.props.children;
  }
}
