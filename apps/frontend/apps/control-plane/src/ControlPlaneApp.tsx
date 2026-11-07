import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router";
import { OperatorSessionProvider } from "@kokonut/operator-client/react";

const FieldOperationsModule = lazy(() =>
  import("./modules/field-operations/FieldOperationsModule")
    .then(({ FieldOperationsModule }) => ({ default: FieldOperationsModule })),
);
const GeneralOperationsModule = lazy(() =>
  import("./modules/general-operations/GeneralOperationsModule")
    .then(({ GeneralOperationsModule }) => ({ default: GeneralOperationsModule })),
);
const GovernanceModule = lazy(() =>
  import("./modules/governance/GovernanceModule")
    .then(({ GovernanceModule }) => ({ default: GovernanceModule })),
);

function WorkspaceLoading() {
  return (
    <main className="main-content" role="status">
      Loading workspace…
    </main>
  );
}

export function ControlPlaneApp() {
  return (
    <OperatorSessionProvider>
      <Routes>
        <Route
          path="/ops/*"
          element={
            <Suspense fallback={<WorkspaceLoading />}>
              <GeneralOperationsModule />
            </Suspense>
          }
        />
        <Route
          path="/field/*"
          element={
            <Suspense fallback={<WorkspaceLoading />}>
              <FieldOperationsModule />
            </Suspense>
          }
        />
        <Route
          path="/governance/*"
          element={
            <Suspense fallback={<WorkspaceLoading />}>
              <GovernanceModule />
            </Suspense>
          }
        />
        <Route path="*" element={<Navigate to="/ops/" replace />} />
      </Routes>
    </OperatorSessionProvider>
  );
}
