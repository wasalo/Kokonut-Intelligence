import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { ControlPlaneApp } from "./ControlPlaneApp";
import "@kokonut/ui/styles.css";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Kokonut Intelligence Control Plane root element is missing");
}

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter>
      <ControlPlaneApp />
    </BrowserRouter>
  </StrictMode>,
);
