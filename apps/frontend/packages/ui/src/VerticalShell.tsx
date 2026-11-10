import { useState, type ReactNode } from "react";
import { Link, NavLink } from "react-router";
import { useOperatorSession } from "@kokonut/operator-client/react";
import { signOutOperatorSession } from "@kokonut/operator-client/request";

const WORKSPACES = [
  { path: "/ops/", label: "General Operations" },
  { path: "/field/", label: "Field Operations" },
  { path: "/governance/", label: "Governance" },
] as const;

function operatorLoginHref(): string {
  const login = new URL("/operator/auth/login", window.location.origin);
  login.searchParams.set("return_to", window.location.pathname);
  login.searchParams.set("prompt", "select_account");
  return `${login.pathname}${login.search}`;
}

export interface NavigationItem {
  to: string;
  label: string;
  end?: boolean;
}

export interface VerticalShellProps {
  name: string;
  summary: string;
  basePath: string;
  navigation: NavigationItem[];
  children: ReactNode;
}

export function VerticalShell({
  name,
  summary,
  basePath,
  navigation,
  children,
}: VerticalShellProps) {
  return (
    <VerticalShellContent
      name={name}
      summary={summary}
      basePath={basePath}
      navigation={navigation}
    >
      {children}
    </VerticalShellContent>
  );
}

function OperatorAccountControl() {
  const session = useOperatorSession();
  const [signingOut, setSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState("");

  async function handleSignOut(switchAccount = false) {
    setSigningOut(true);
    setSignOutError("");
    try {
      await signOutOperatorSession();
      if (switchAccount) window.location.assign(operatorLoginHref());
      else window.location.reload();
    } catch {
      setSigningOut(false);
      setSignOutError("Sign out could not be completed. Try again.");
    }
  }

  if (session.status === "loading") {
    return <span className="operator-account__status" role="status">Checking session…</span>;
  }

  if (session.status === "signed-out") {
    return <a className="operator-account__action" href={operatorLoginHref()}>Sign in</a>;
  }

  if (session.status === "error") {
    return (
      <span className="operator-account__error" role="alert">
        Session unavailable. <button type="button" onClick={() => window.location.reload()}>Retry</button>
      </span>
    );
  }

  const name = session.session.operator.display_name || session.session.operator.email || "Operator";
  return (
    <div className="operator-account">
      <span className="operator-account__name" title={name}>{name}</span>
      <button
        className="operator-account__action"
        type="button"
        onClick={() => void handleSignOut()}
        disabled={signingOut}
      >
        {signingOut ? "Signing out…" : "Sign out"}
      </button>
      <button
        className="operator-account__action"
        type="button"
        onClick={() => void handleSignOut(true)}
        disabled={signingOut}
      >
        {signingOut ? "Switching…" : "Switch account"}
      </button>
      {signOutError ? <span className="operator-account__error" role="alert">{signOutError}</span> : null}
    </div>
  );
}

function VerticalShellContent({
  name,
  summary,
  basePath,
  navigation,
  children,
}: VerticalShellProps) {
  return (
    <div className="ki-app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="app-header">
        <Link className="brand-lockup" to={basePath} aria-label={`${name} home`}>
          <span className="brand-mark" aria-hidden="true">K</span>
          <span className="brand-copy">
            <span className="brand-name">Kokonut Intelligence</span>
            <span className="brand-vertical">{name}</span>
          </span>
        </Link>
        <p className="header-summary">{summary}</p>
        <OperatorAccountControl />
      </header>

      <nav className="vertical-switcher" aria-label="Kokonut workspaces">
        {WORKSPACES.map(({ path, label }) => {
          const isCurrent = basePath === path;
          return (
            <Link
              key={path}
              to={path}
              className={
                isCurrent
                  ? "vertical-switcher__link is-current"
                  : "vertical-switcher__link"
              }
              aria-current={isCurrent ? "page" : undefined}
            >
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="app-layout">
        <nav className="primary-navigation" aria-label={`${name} navigation`}>
          {navigation.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                isActive ? "navigation-link is-active" : "navigation-link"
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <main id="main-content" className="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
      <footer className="app-footer">
        <span>Kokonut Intelligence</span>
        <span>Access and actions are checked by the Gateway.</span>
      </footer>
    </div>
  );
}
