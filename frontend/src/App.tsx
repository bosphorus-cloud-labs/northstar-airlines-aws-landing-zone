import {
  Activity,
  ArrowUpRight,
  ChevronRight,
  Clock3,
  GitCompareArrows,
  LayoutDashboard,
  Layers3,
  Menu,
  Navigation,
  RefreshCw,
  ShieldCheck,
  ShieldQuestion,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { request, useDataset, ApiError } from "./api/client";
import { governanceApiMode } from "./api/capabilities";
import { AccountDetail, Accounts } from "./pages/Accounts";
import { Compliance } from "./pages/Compliance";
import { Deployments, Drift, Exceptions } from "./pages/Operations";
import { Overview } from "./pages/Overview";
import { ConsoleBoundary } from "./components/ConsoleBoundary";
import { Empty } from "./components/ui";
import { useSession } from "./auth/context";
import {
  DEFAULT_SELECTION,
  SelectionContext,
  useSelection,
  type Selection,
} from "./api/selection";
const navigation = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/accounts", label: "Accounts", icon: Layers3 },
  { to: "/compliance", label: "Compliance", icon: ShieldCheck },
  { to: "/deployments", label: "Deployments", icon: Activity },
  { to: "/drift", label: "Configuration Drift", icon: GitCompareArrows },
  { to: "/exceptions", label: "Governance Exceptions", icon: ShieldQuestion },
];
export function App() {
  const [requested, setSelection] = useState("current");
  const baselineMode = governanceApiMode() === "baseline-v1";
  const catalog = useQuery({
    queryKey: ["version-catalog", baselineMode],
    queryFn: ({ signal }) =>
      request(
        "/api/v1/summary",
        signal,
        baselineMode ? {} : { catalog: "true" },
      ),
    retry: false,
    staleTime: 30000,
  });
  const versions =
    catalog.data && "versions" in catalog.data.data
      ? catalog.data.data.versions
      : [DEFAULT_SELECTION];
  const current =
    catalog.data && "current" in catalog.data.data
      ? catalog.data.data.current
      : DEFAULT_SELECTION;
  const currentUnavailable =
    catalog.isError ||
    (!baselineMode && catalog.isSuccess && !("current" in catalog.data.data));
  const currentRun =
    catalog.data && "current_run" in catalog.data.data
      ? catalog.data.data.current_run
      : null;
  const currentMode =
    requested === "current" ||
    !versions.some((v) => v.policy_version === requested);
  const selection = {
    ...(currentMode
      ? current
      : (versions.find((v) => v.policy_version === requested) ?? current)),
    ready: !catalog.isPending && (!currentUnavailable || !currentMode),
  };
  return (
    <SelectionContext.Provider value={selection}>
      <Workspace
        baselineMode={baselineMode}
        versions={versions}
        change={setSelection}
        currentMode={currentMode}
        currentRun={currentRun}
        catalogError={currentUnavailable}
        catalogMessage={
          catalog.error instanceof ApiError
            ? catalog.error.message
            : "The server did not return a current governance marker."
        }
      />
    </SelectionContext.Provider>
  );
}
function Workspace({
  baselineMode,
  versions,
  change,
  catalogError,
  catalogMessage,
  currentMode,
  currentRun,
}: {
  baselineMode: boolean;
  versions: Selection[];
  change: (value: string) => void;
  currentMode: boolean;
  currentRun: string | null;
  catalogError: boolean;
  catalogMessage: string;
}) {
  const selection = useSelection();
  const session = useSession();
  const [menu, setMenu] = useState(false);
  const location = useLocation();
  const client = useQueryClient();
  const query = useDataset();
  const journal =
    query.data && "journal" in query.data.summary
      ? query.data.summary.journal
      : [];
  const environmentProfiles =
    query.data && "environment_requirements" in query.data.summary
      ? query.data.summary.environment_requirements
      : null;
  const latestDeployment = query.data
    ? [...query.data.deployments].sort(
        (a, b) =>
          b.started_at.localeCompare(a.started_at) || b.id.localeCompare(a.id),
      )[0]
    : undefined;
  const title =
    navigation.find((item) => item.to === location.pathname)?.label ??
    (location.pathname.startsWith("/accounts/")
      ? "Account details"
      : "Page not found");
  useEffect(() => {
    document.title = `${title} · NorthStar Governance`;
    document.querySelector<HTMLElement>("main h1")?.focus();
  }, [location.pathname, title]);
  useEffect(() => {
    if (!menu) return;
    const previous = document.activeElement as HTMLElement | null;
    const sidebar = document.getElementById("workspace-navigation");
    const links = Array.from(
      sidebar?.querySelectorAll<HTMLElement>("a, button") ?? [],
    );
    links[0]?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setMenu(false);
        previous?.focus();
      }
      if (event.key === "Tab" && links.length) {
        if (event.shiftKey && document.activeElement === links[0]) {
          event.preventDefault();
          links.at(-1)?.focus();
        } else if (!event.shiftKey && document.activeElement === links.at(-1)) {
          event.preventDefault();
          links[0]?.focus();
        }
      }
    };
    document.addEventListener("keydown", keydown);
    return () => document.removeEventListener("keydown", keydown);
  }, [menu]);
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      {menu && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setMenu(false)}
        />
      )}
      <aside
        className={`sidebar ${menu ? "is-open" : ""}`}
        id="workspace-navigation"
      >
        <Link
          to="/"
          className="brand"
          aria-label="NorthStar Airlines home"
          onClick={() => setMenu(false)}
        >
          <span className="brand-symbol">
            <Navigation size={25} fill="currentColor" />
          </span>
          <span>
            NorthStar<small>A I R L I N E S</small>
          </span>
        </Link>
        <div className="workspace-switch">
          <div className="workspace-initials">NS</div>
          <div>
            <strong>Governance console</strong>
            <small>
              {session.mode === "local"
                ? "Local demonstration"
                : "Authenticated POC"}
            </small>
          </div>
          <span className="workspace-dot" />
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav aria-label="Main navigation">
          {navigation.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
              onClick={() => setMenu(false)}
            >
              <Icon size={18} />
              <span>{label}</span>
              <ChevronRight size={13} className="nav-chevron" />
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="baseline-note">
            <ShieldCheck size={20} />
            <strong>Governance by design</strong>
            <p>
              Preventive intent.
              <br />
              Detective evidence.
              <br />
              Controlled delivery.
            </p>
          </div>
          <div className="region-label">
            <span />
            eu-central-1 <small>POC target region</small>
          </div>
          <p className="sidebar-foot">NorthStar case study · v0.1</p>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Toggle navigation"
              aria-expanded={menu}
              aria-controls="workspace-navigation"
              onClick={() => setMenu(!menu)}
            >
              {menu ? <X size={20} /> : <Menu size={20} />}
            </button>
            <span>Workspace</span>
            <ChevronRight size={12} />
            <strong>NorthStar Airlines</strong>
            <ChevronRight size={12} />
            <span>{title}</span>
          </div>
          <div className="topbar-right">
            <span
              className={`api-indicator ${query.isSuccess && !query.isError ? "connected" : ""}`}
            >
              <i />
              {query.isError
                ? "API unavailable"
                : query.isPending
                  ? "Connecting to API"
                  : session.mode === "local"
                    ? "Local API"
                    : "Governance API"}
            </span>
            {session.signOut && (
              <button className="button" onClick={session.signOut}>
                Sign out
              </button>
            )}
            <div
              className="reader-avatar"
              title={
                session.mode === "local"
                  ? "Local demo reader"
                  : "Signed-in governance reader"
              }
            >
              NS
            </div>
          </div>
        </header>
        <div className="simulation-banner">
          <span className="simulation-label">
            <span />
            SIMULATED DATA
          </span>
          <p>
            Synthetic fleet and evidence. No real AWS compliance is being
            assessed.
          </p>
          <span className="banner-mode">
            {session.mode === "local" ? "LOCAL DEMO" : "AUTHENTICATED POC"}
          </span>
        </div>
        <main id="main-content">
          {baselineMode && (
            <div className="info-strip" role="status">
              <p>
                <strong>V1 backend compatibility mode.</strong> Showing the
                API's fixed baseline evaluation. Current governance markers, V2
                rollout history and historical snapshot selection remain
                unavailable until the separate backend upgrade. This mode never
                substitutes data after an authentication or API error.
              </p>
            </div>
          )}
          <div className="evaluation-toolbar">
            <label className="policy-selector">
              {baselineMode ? "Baseline evaluation" : "Historical snapshot"}
              <select
                disabled={baselineMode}
                aria-label={
                  baselineMode ? "Baseline evaluation" : "Historical snapshot"
                }
                value={currentMode ? "current" : selection.policy_version}
                onChange={(event) => change(event.target.value)}
              >
                <option value="current">
                  {baselineMode
                    ? "Baseline policy 1.0.0"
                    : "Current governance"}
                </option>
                {!baselineMode &&
                  versions.map((v) => (
                    <option
                      key={v.snapshot_id ?? v.policy_version}
                      value={v.policy_version}
                    >
                      Policy {v.policy_version} ·{" "}
                      {new Date(v.evaluated_at)
                        .toISOString()
                        .slice(0, 16)
                        .replace("T", " ")}{" "}
                      UTC · {v.snapshot_id?.slice(0, 8) ?? "baseline"}
                    </option>
                  ))}
              </select>
              <small>
                {baselineMode
                  ? "V1 compatibility · history unavailable"
                  : "Read-only history"}
                {catalogError ? " · current marker unavailable" : ""}
              </small>
            </label>
            <span>
              <Clock3 size={14} />
              Reference evaluation{" "}
              <strong>
                {selection.ready === false
                  ? "Resolving…"
                  : new Intl.DateTimeFormat("en-GB", {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                      timeZone: "UTC",
                      hour12: false,
                    }).format(new Date(selection.evaluated_at))}{" "}
                UTC
              </strong>
            </span>
            <button
              className="button refresh-button"
              disabled={query.isFetching}
              onClick={() => {
                change("current");
                void client.invalidateQueries();
              }}
            >
              <RefreshCw size={14} className={query.isFetching ? "spin" : ""} />
              Refresh current state
            </button>
          </div>
          <div className="governance-state-header" aria-live="polite">
            <strong>
              {catalogError && currentMode
                ? baselineMode
                  ? "Baseline unavailable"
                  : "Current state unavailable"
                : selection.ready === false
                  ? "Resolving current governance"
                  : `${baselineMode ? "BASELINE EVALUATION" : currentMode ? "CURRENT GOVERNANCE" : "HISTORICAL EVALUATION"} · Policy revision ${selection.policy_version}`}
            </strong>
            {selection.ready !== false && (
              <span>
                Latest deployment run:{" "}
                {(currentMode && currentRun) ||
                  latestDeployment?.correlation_id ||
                  "Baseline inventory"}
              </span>
            )}
            {!currentMode && (
              <small>
                Historical comparison only. No rollback or deployment is
                performed.
              </small>
            )}
          </div>
          {journal.length > 0 && (
            <details className="rollout-story" open>
              <summary>
                SIMULATED policy rollout · Policy {selection.policy_version} ·{" "}
                {journal.length} recorded stages
              </summary>
              <div className="rollout-stages">
                {[
                  "policy.validated",
                  "policy.approved",
                  "canary.passed",
                  "rollout.blocked",
                  "rollout.completed",
                  "account.activated",
                ].map((action) => {
                  const stage = journal.find((e) => e.action === action);
                  return (
                    <span
                      key={action}
                      className={
                        stage
                          ? action === "rollout.blocked"
                            ? "stage-warning"
                            : "stage-complete"
                          : ""
                      }
                    >
                      {action.replaceAll(".", " ")}
                      {stage && (
                        <small>
                          {new Date(stage.at).toISOString().slice(11, 16)} UTC
                        </small>
                      )}
                    </span>
                  );
                })}
              </div>
              <p>
                Real Terraform planning verified the desired configuration.
                Approval, AFT distribution, failure/retry, and evidence are
                simulated. Successful distribution does not imply compliance.
              </p>
            </details>
          )}
          {environmentProfiles && (
            <details className="environment-profiles">
              <summary>
                Environment-specific governance · central baseline inherited
              </summary>
              <div className="rollout-stages">
                {Object.entries(environmentProfiles).map(
                  ([environment, requirements]) => {
                    const approval = requirements?.find(
                      (r) => r.control_id === "deployment-approval",
                    );
                    return (
                      <span key={environment}>
                        {environment}
                        <small>
                          Approval configuration:{" "}
                          {approval?.expected ? "required" : "not required"}
                        </small>
                        <small>
                          Approval evidence age: {approval?.max_age_hours}h ·{" "}
                          {requirements?.length} controls
                        </small>
                      </span>
                    );
                  },
                )}
              </div>
            </details>
          )}
          {catalogError && currentMode ? (
            <div className="error-state" role="alert">
              <h2>
                {baselineMode
                  ? "Baseline evaluation could not be loaded"
                  : "Current governance could not be resolved"}
              </h2>
              <p>{catalogMessage}</p>
              <p>
                {baselineMode
                  ? "Refresh after checking API access. No alternate data source is used."
                  : "Refresh or explicitly choose a historical snapshot. Historical data is not substituted for CURRENT."}
              </p>
              <button
                className="button primary"
                onClick={() => void client.invalidateQueries()}
              >
                Try again
              </button>
            </div>
          ) : (
            <ConsoleBoundary
              key={`${selection.policy_version}|${location.pathname}`}
            >
              <div key={selection.policy_version}>
                <Routes>
                  <Route path="/" element={<Overview />} />
                  <Route path="/accounts" element={<Accounts />} />
                  <Route
                    path="/accounts/:accountId"
                    element={<AccountDetail />}
                  />
                  <Route path="/compliance" element={<Compliance />} />
                  <Route path="/deployments" element={<Deployments />} />
                  <Route path="/drift" element={<Drift />} />
                  <Route path="/exceptions" element={<Exceptions />} />
                  <Route
                    path="*"
                    element={
                      <>
                        <h1>Page not found</h1>
                        <Empty message="This page is not part of the governance workspace." />
                        <Link className="text-link" to="/">
                          Return to overview <ArrowUpRight size={15} />
                        </Link>
                      </>
                    }
                  />
                </Routes>
              </div>
            </ConsoleBoundary>
          )}
          <footer className="workspace-footer">
            <span>
              NorthStar Airlines <i /> Governance Console
            </span>
            <span>Read-only · Simulated multi-account fleet</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
