import { Component } from "react";

/**
 * A render error anywhere below this point used to unmount the entire app,
 * leaving a blank page with no explanation. Catch it, show something
 * actionable, and keep the rest of the shell (nav, routing) alive.
 */
export default class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Render error:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="card empty">
        <div className="display">
          Something <em>broke</em> on this screen.
        </div>
        <p className="dim" style={{ marginTop: 8 }}>
          The rest of the app is still running — this panel failed to render.
        </p>
        <p className="faint" style={{ marginTop: 6 }}>
          {String(this.state.error?.message || this.state.error)}
        </p>
        <div className="row" style={{ justifyContent: "center", marginTop: 16 }}>
          <button onClick={() => this.setState({ error: null })}>Try again</button>
          <button className="ghost" onClick={() => window.location.reload()}>
            Reload
          </button>
        </div>
      </div>
    );
  }
}
