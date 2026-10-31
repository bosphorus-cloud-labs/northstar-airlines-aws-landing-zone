import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthGate } from "./auth/AuthGate";
import { runtimeConfig } from "./auth/config";
import { App } from "./App";
import "./styles.css";
const queryClient = new QueryClient();
let content;
try {
  content = (
    <AuthGate config={runtimeConfig()}>
      <App />
    </AuthGate>
  );
} catch {
  content = (
    <main className="error-state" role="alert">
      <h1>Deployment configuration required</h1>
      <p>
        This build requires the public Cognito and API settings exported by
        Terraform. No local-demo fallback or API requests are enabled.
      </p>
    </main>
  );
}
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{content}</BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
