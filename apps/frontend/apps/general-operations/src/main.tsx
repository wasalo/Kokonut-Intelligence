import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { GeneralOperationsApp } from "./GeneralOperationsApp";
import "@kokonut/ui/styles.css";
import "./app.css";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("General Operations root element is missing");
}

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter basename="/ops">
      <GeneralOperationsApp />
    </BrowserRouter>
  </StrictMode>,
);
