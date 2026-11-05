import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { GovernanceApp } from "./GovernanceApp";
import "@kokonut/ui/styles.css";
import "./app.css";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Governance root element is missing");
}

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter basename="/governance">
      <GovernanceApp />
    </BrowserRouter>
  </StrictMode>,
);
