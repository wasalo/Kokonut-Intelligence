import { lazy, Suspense, useEffect } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router";
import { OperatorSessionProvider } from "@kokonut/operator-client/react";
import { PublicEcosystemPage } from "./modules/public-home/PublicEcosystemPage";

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
  const { pathname } = useLocation();

  useEffect(() => {
    document.title = pathname === "/"
      ? "Kokonut Intelligence · A clearer view of a regenerative network"
      : "Kokonut Intelligence · Control Plane";
  }, [pathname]);

  return (
    <Routes>
      <Route path="/" element={<PublicEcosystemPage />} />
      <Route element={<OperatorSessionProvider><Outlet /></OperatorSessionProvider>}>
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
      </Route>
      <Route path="*" element={<Navigate to="/ops/" replace />} />
    </Routes>
  );
}
