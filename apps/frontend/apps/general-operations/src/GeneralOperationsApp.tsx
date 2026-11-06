import { Link, Route, Routes } from "react-router";
import { VerticalShell, type NavigationItem } from "@kokonut/ui";
import { ReportReviewPage } from "./ReportReviewPage";
import { MetricListPage } from "./MetricListPage";
import { CoordinationSummaryPage } from "./CoordinationSummaryPage";

const navigation: NavigationItem[] = [
  { to: "/", label: "Overview", end: true },
  { to: "/reports", label: "Report review" },
  { to: "/metrics", label: "Metrics" },
  { to: "/programs", label: "Programs and solutions" },
  { to: "/planning", label: "Planning and coordination" },
  { to: "/insights", label: "Insights and analysis" },
  { to: "/administration", label: "Administration" },
];

function GeneralOperationsHome() {
  return (
    <section aria-labelledby="operations-home-heading">
      <p className="eyebrow">General Operations</p>
      <h2 id="operations-home-heading">Coordinate work across Kokonut Intelligence</h2>
      <p className="lead">
        Reports, planning, programs, and analysis are being moved into this
        modular workspace. The current operator console remains available while
        each workflow is migrated and accepted.
      </p>
      <div className="workflow-grid">
        <article className="workflow-card">
          <div>
            <p className="eyebrow">Existing workspace</p>
            <h3>Operator console</h3>
            <p>Continue current location-scoped operations and review workflows.</p>
          </div>
          <a className="button-link" href="/operator/">Open current console</a>
        </article>
        <article className="workflow-card workflow-card-muted">
          <div>
            <p className="eyebrow">Next migration slices</p>
            <h3>Reports, planning, and analysis</h3>
            <p>
              The legacy feature inventory is mapped to direct routes before the
              corresponding workflow is replaced.
            </p>
          </div>
          <span className="status-label">In migration</span>
        </article>
      </div>
      <p className="migration-note" role="note">
        This candidate shell does not grant access. The Gateway continues to
        enforce operator identity, capabilities, and location scope.
      </p>
    </section>
  );
}

function WorkflowLanding({ title, description }: { title: string; description: string }) {
  return (
    <section aria-labelledby="workflow-heading">
      <p className="eyebrow">General Operations</p>
      <h2 id="workflow-heading">{title}</h2>
      <p className="lead">{description}</p>
      <p className="migration-note" role="status">
        This route is reserved for the feature-preserving migration. Existing
        workflows are still available in the operator console.
      </p>
      <a className="button-link" href="/operator/">Open current console</a>
    </section>
  );
}

export function GeneralOperationsApp() {
  return (
    <VerticalShell
      name="General Operations"
      summary="Reports, programs, planning, and analysis"
      basePath="/ops/"
      navigation={navigation}
    >
      <Routes>
        <Route path="/" element={<GeneralOperationsHome />} />
        <Route path="/reports" element={<ReportReviewPage />} />
        <Route path="/metrics" element={<MetricListPage />} />
        <Route path="/planning" element={<CoordinationSummaryPage />} />
        <Route
          path="/programs"
          element={<WorkflowLanding title="Programs and solutions" description="Coordinate operating programs and solution lifecycles." />}
        />
        <Route
          path="/insights"
          element={<WorkflowLanding title="Insights and analysis" description="Explore location-scoped trends and analytical summaries." />}
        />
        <Route
          path="/administration"
          element={<WorkflowLanding title="Administration" description="Manage operational review workflows within your assigned capabilities." />}
        />
        <Route path="*" element={<section><h2>Page not found</h2><Link to="/">Return to overview</Link></section>} />
      </Routes>
    </VerticalShell>
  );
}
