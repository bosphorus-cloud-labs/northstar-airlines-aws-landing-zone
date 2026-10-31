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
import { useQueryClient } from "@tanstack/react-query";
import { REFERENCE_AT, useDataset } from "./api/client";
import { AccountDetail, Accounts } from "./pages/Accounts";
import { Compliance } from "./pages/Compliance";
import { Deployments, Drift, Exceptions } from "./pages/Operations";
import { Overview } from "./pages/Overview";
import { ConsoleBoundary } from "./components/ConsoleBoundary";
import { Empty } from "./components/ui";
import { useSession } from "./auth/context";
const navigation = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/accounts", label: "Accounts", icon: Layers3 },
  { to: "/compliance", label: "Compliance", icon: ShieldCheck },
  { to: "/deployments", label: "Deployments", icon: Activity },
  { to: "/drift", label: "Configuration Drift", icon: GitCompareArrows },
  { to: "/exceptions", label: "Governance Exceptions", icon: ShieldQuestion },
];
export function App() {
  const session = useSession();
  const [menu, setMenu] = useState(false);
  const location = useLocation();
  const client = useQueryClient();
  const query = useDataset();
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
          <div className="evaluation-toolbar">
            <span>
              <Clock3 size={14} />
              Reference evaluation{" "}
              <strong>
                {new Intl.DateTimeFormat("en-GB", {
                  day: "2-digit",
                  month: "short",
                  year: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                  timeZone: "UTC",
                  hour12: false,
                }).format(new Date(REFERENCE_AT))}{" "}
                UTC
              </strong>
            </span>
            <button
              className="button refresh-button"
              disabled={query.isFetching}
              onClick={() => void client.invalidateQueries()}
            >
              <RefreshCw size={14} className={query.isFetching ? "spin" : ""} />
              Refresh snapshot
            </button>
          </div>
          <ConsoleBoundary key={location.pathname}>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/accounts" element={<Accounts />} />
              <Route path="/accounts/:accountId" element={<AccountDetail />} />
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
          </ConsoleBoundary>
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
