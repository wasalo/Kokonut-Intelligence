import type { ReactNode } from "react";
import { NavLink } from "react-router";

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
    <div className="ki-app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="app-header">
        <a className="brand-lockup" href={basePath} aria-label={`${name} home`}>
          <span className="brand-mark" aria-hidden="true">K</span>
          <span className="brand-copy">
            <span className="brand-name">Kokonut Intelligence</span>
            <span className="brand-vertical">{name}</span>
          </span>
        </a>
        <p className="header-summary">{summary}</p>
      </header>

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
