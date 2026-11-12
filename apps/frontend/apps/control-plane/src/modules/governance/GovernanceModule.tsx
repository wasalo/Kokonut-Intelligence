import { Link, Navigate, Route, Routes } from "react-router";
import { useEffect } from "react";
import { VerticalShell, type NavigationItem } from "@kokonut/ui";
import { DelphiRecommendationReviewPage } from "./DelphiRecommendationReviewPage";
import "./app.css";

const navigation: NavigationItem[] = [
  { to: "/governance/", label: "Overview", end: true },
  { to: "/governance/workflows", label: "Governance workflows" },
  { to: "/governance/deliberation", label: "Delphi studies" },
  { to: "/governance/recommendations", label: "Recommendation review" },
  { to: "/governance/participate", label: "Participant entry" },
];

function GovernanceHome() {
  return (
    <section aria-labelledby="governance-home-heading">
      <p className="eyebrow">Governance</p>
      <h2 id="governance-home-heading">Make decisions with clear roles and review</h2>
      <p className="lead">
        Governance roles, deliberation, consent, minority reports, and
        facilitator recommendations belong in one vertical, with distinct
        operator and participant experiences.
      </p>
      <div className="governance-links">
        <article>
          <h3>Governance operations</h3>
          <p>Current role, tension, assignment, and tactical workflows.</p>
          <a className="secondary-action" href="/operator/">Open current operator console</a>
        </article>
        <article>
          <h3>Delphi participant</h3>
          <p>Open a private study invite and review its consent notice.</p>
          <a className="primary-action" href="/participation/delphi">Open participant app</a>
        </article>
      </div>
      <p className="migration-note" role="note">
        Participant invite credentials remain in the URL fragment and are
        removed by the participant app before its API requests.
      </p>
    </section>
  );
}

function GovernanceLanding({ title, description }: { title: string; description: string }) {
  return (
    <section aria-labelledby="governance-route-heading">
      <p className="eyebrow">Governance</p>
      <h2 id="governance-route-heading">{title}</h2>
      <p className="lead">{description}</p>
      <p className="migration-note" role="status">
        The current governance workflows remain available until their new
        screens preserve the decision, consent, review, and publication rules.
      </p>
      <a className="secondary-action" href="/operator/">Open current operator console</a>
    </section>
  );
}

function ParticipantCompatibilityEntry() {
  useEffect(() => {
    const fragment = window.location.hash;
    const destination = new URL("/participation/delphi", window.location.origin);
    destination.hash = fragment.slice(1);
    window.location.replace(destination.href);
  }, []);

  return (
    <section aria-live="polite">
      <p>Opening the Delphi participant experience…</p>
    </section>
  );
}

export function GovernanceModule() {
  return (
    <VerticalShell
      name="Governance"
      summary="Roles, deliberation, and accountable decisions"
      basePath="/governance/"
      navigation={navigation}
    >
      <Routes>
        <Route index element={<GovernanceHome />} />
        <Route
          path="workflows"
          element={<GovernanceLanding title="Governance workflows" description="Review tensions, roles, assignments, and tactical decisions." />}
        />
        <Route
          path="deliberation"
          element={<GovernanceLanding title="Delphi studies" description="Create studies, govern notices, invite participants, and review recommendations." />}
        />
        <Route path="recommendations" element={<DelphiRecommendationReviewPage />} />
        <Route path="participate" element={<ParticipantCompatibilityEntry />} />
        <Route path="participant" element={<Navigate to="/governance/participate" replace />} />
        <Route path="*" element={<section><h2>Page not found</h2><Link to="/governance/">Return to overview</Link></section>} />
      </Routes>
    </VerticalShell>
  );
}
