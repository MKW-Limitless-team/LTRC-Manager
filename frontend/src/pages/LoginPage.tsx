import { useQuery } from "@tanstack/react-query";
import { Navigate, useSearchParams } from "react-router-dom";

import { getLoginUrl, getSessionState } from "../lib/api";

export function LoginPage() {
  const [searchParams] = useSearchParams();
  const error = searchParams.get("error");
  const sessionQuery = useQuery({
    queryKey: ["session"],
    queryFn: getSessionState
  });

  if (sessionQuery.data?.authenticated && sessionQuery.data.user?.authorized) {
    return <Navigate to="/app" replace />;
  }

  return (
    <main className="page-shell">
      <section className="auth-card">
        <div className="auth-copy">
          <p className="eyebrow">LTRC Manager</p>
          <h1>Discord Login</h1>
          <p className="lead">
            Sign in with your Discord account to access the LTRC workflow.
          </p>
        </div>
        {error ? (
          <div className="error-banner">
            {error === "not_allowed"
              ? "You are not authorised to use LTRC Manager. Contact Blazico if this is a mistake."
              : "Login could not be completed."}
          </div>
        ) : null}
        <div className="auth-actions">
          <a className="primary-button auth-button" href={getLoginUrl()}>
            Continue with Discord
          </a>
        </div>
      </section>
    </main>
  );
}
