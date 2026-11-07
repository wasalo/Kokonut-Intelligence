import { Link, Route, Routes } from "react-router";
import { VerticalShell, type NavigationItem } from "@kokonut/ui";
import { FarmActivityListPage } from "./FarmActivityListPage";
import "./app.css";

const navigation: NavigationItem[] = [
  { to: "/field/", label: "Overview", end: true },
  { to: "/field/collector", label: "Field Collector" },
  { to: "/field/records", label: "Farm records" },
  { to: "/field/supervision", label: "Device supervision" },
];

function FieldOperationsHome() {
  return (
    <section aria-labelledby="field-home-heading">
      <p className="eyebrow">Field Operations</p>
      <h2 id="field-home-heading">Work reliably in the field, online or offline</h2>
      <p className="lead">
        The Field Collector stays a dedicated offline-first experience. This
        workspace will bring its enrollment, review, and location-scoped farm
        workflows together without changing the collection protocol.
      </p>
      <div className="field-actions">
        <a className="primary-action" href="/api/mobile/app">Open Field Collector</a>
        <a className="secondary-action" href="/operator/">Open supervisor console</a>
      </div>
      <div className="field-feature-list" aria-label="Field Operations migration areas">
        <article><h3>Collect</h3><p>Encrypted offline notes, forms, photos, and retry-safe sync.</p></article>
        <article><h3>Review</h3><p>Location-scoped intake, farm activity, and collection disposition.</p></article>
        <article><h3>Monitor</h3><p>Traceability, harvests, energy, water, landscape, waste, and nutrients.</p></article>
      </div>
      <p className="migration-note" role="note">
        Current Field Collector and supervisor tools remain available while
        their routes are migrated and accepted.
      </p>
    </section>
  );
}

function FieldLanding({ title, description }: { title: string; description: string }) {
  return (
    <section aria-labelledby="field-route-heading">
      <p className="eyebrow">Field Operations</p>
      <h2 id="field-route-heading">{title}</h2>
      <p className="lead">{description}</p>
      <p className="migration-note" role="status">
        This route will replace the matching legacy workflow only after its
        location, consent, and offline behavior have parity evidence.
      </p>
      <Link className="secondary-action" to="/field/">Return to Field Operations</Link>
    </section>
  );
}

export function FieldOperationsModule() {
  return (
    <VerticalShell
      name="Field Operations"
      summary="Collection, devices, and farm workflows"
      basePath="/field/"
      navigation={navigation}
    >
      <Routes>
        <Route index element={<FieldOperationsHome />} />
        <Route
          path="collector"
          element={<FieldLanding title="Field Collector" description="Use the current offline-first mobile collector." />}
        />
        <Route
          path="records"
          element={<FarmActivityListPage />}
        />
        <Route
          path="supervision"
          element={<FieldLanding title="Device supervision" description="Enrollment, inventory, and content-free collection monitoring." />}
        />
        <Route path="*" element={<section><h2>Page not found</h2><Link to="/field/">Return to overview</Link></section>} />
      </Routes>
    </VerticalShell>
  );
}
