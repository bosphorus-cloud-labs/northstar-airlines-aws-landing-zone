import { useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Menu, Navigation, RefreshCw, X } from "lucide-react";
import {
  accountRecords,
  resourceState,
  type ResourceData,
} from "./api/resources";
import { Badge } from "./components/ui";
import { useSession } from "./auth/context";
const navigation = [
  ["/", "Overview"],
  ["/accounts", "Accounts"],
  ["/resources", "Resources & drift"],
  ["/compliance", "Compliance"],
  ["/deployments", "Deployment activity"],
  ["/exceptions", "Governance exceptions"],
];
const readable = (value: unknown) =>
  value === null ? "Missing evidence" : String(value);
const environment = (value: string) =>
  value === "pre-production"
    ? "Pre-Production"
    : value
        .split("-")
        .map((s) => s[0].toUpperCase() + s.slice(1))
        .join(" ");
export function ResourceConsole() {
  const query = useQuery({
    queryKey: ["resource-current"],
    queryFn: ({ signal }) => resourceState(signal),
    retry: false,
    refetchOnWindowFocus: false,
  });
  const [menu, setMenu] = useState(false);
  const session = useSession();
  const client = useQueryClient();
  const path = useLocation().pathname;
  return (
    <div className="app-shell resource-console">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <aside
        className={`sidebar ${menu ? "is-open" : ""}`}
        aria-label="Main navigation"
      >
        <Link className="brand" to="/">
          <Navigation aria-hidden="true" />
          <span>
            NorthStar Airlines<small>Governance Operations</small>
          </span>
        </Link>
        <button
          className="mobile-menu"
          aria-label="Close navigation"
          onClick={() => setMenu(false)}
        >
          <X />
        </button>
        <nav>
          {navigation.map(([to, label]) => (
            <NavLink
              end={to === "/"}
              key={to}
              to={to}
              onClick={() => setMenu(false)}
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <strong>SIMULATED AWS DATA</strong>
          <p>
            Read-only governance console
            <br />
            Frankfurt · eu-central-1
          </p>
          {session.signOut && (
            <button onClick={session.signOut}>Sign out</button>
          )}
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <button
            className="mobile-menu"
            aria-label="Open navigation"
            onClick={() => setMenu(true)}
          >
            <Menu />
          </button>
          <span>NorthStar / Governance</span>
          <span className="simulation-badge">SIMULATED DATA</span>
          <button
            onClick={() => {
              void query.refetch();
              void client.invalidateQueries({
                queryKey: ["account-operations"],
              });
            }}
            disabled={query.isFetching}
          >
            <RefreshCw size={15} aria-hidden="true" /> Refresh
          </button>
        </header>
        <main id="main-content" className="content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">CURRENT GOVERNANCE STATE</p>
              <h1>
                {navigation.find(([to]) => to === path)?.[1] ??
                  "Account details"}
              </h1>
              <p>
                Real application, Terraform validation and protected
                publication. Synthetic accounts, configuration and evidence.
              </p>
            </div>
          </div>
          {query.isPending ? (
            <p role="status">Loading current compliance evidence…</p>
          ) : query.isError ? (
            <div role="alert" className="error-state">
              <h2>Compliance data unavailable</h2>
              <p>{query.error.message}</p>
              <button onClick={() => void query.refetch()}>Try again</button>
            </div>
          ) : (
            <>
              <p className="resource-context">
                Evaluating {query.data.data.summary.accounts} synthetic AWS
                accounts across four environments. · Evidence evaluation:{" "}
                {query.data.data.evaluated_at} ·{" "}
                {query.data.metadata.published_at
                  ? `Published ${query.data.metadata.published_at}`
                  : "Local fixture — not published"}
              </p>
              {path === "/" ? (
                <Overview data={query.data.data} />
              ) : path === "/accounts" || path.startsWith("/accounts/") ? (
                <Accounts data={query.data.data} path={path} />
              ) : path === "/exceptions" ? (
                <AccountOperations exceptions />
              ) : path === "/deployments" ? (
                <Activity data={query.data.data} />
              ) : path === "/compliance" ? (
                <Compliance data={query.data.data} />
              ) : (
                <Resources data={query.data.data} />
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
function approvalIntent(data: ResourceData, env: string) {
  if (!data.terraform_validation) return "Not planned for local fixture";
  const accounts = Object.values(data.terraform_validation.accounts).filter(
    (account) => account.environment === env,
  );
  if (!accounts.length) return "No target accounts";
  return accounts.every((account) => account.approval_required)
    ? "Required by Terraform baseline"
    : "Standard CI validation";
}
function Overview({ data }: { data: ResourceData }) {
  return (
    <>
      <div className="resource-metrics">
        {Object.entries(data.summary).map(([name, value]) => (
          <section className="panel" key={name}>
            <p>
              {["compliant", "noncompliant", "unknown", "stale"].includes(name)
                ? `${environment(name)} resources`
                : environment(name)}
            </p>
            <strong>{value}</strong>
          </section>
        ))}
      </div>
      <section className="panel">
        <h2>What needs attention</h2>
        <p>
          Configuration distribution is separate from compliance. Missing and
          stale observations never pass a control.
        </p>
        {data.findings
          .filter((f) => f.status !== "compliant")
          .slice(0, 5)
          .map((f) => (
            <article className="resource-issue" key={f.id}>
              <Badge status={f.status} />
              <strong>
                {data.resources.find((r) => r.id === f.resource_id)?.name}
              </strong>
              <p>
                {f.control}: {f.reason}
              </p>
              <Link to={`/accounts/${f.account_id}`}>
                {f.account_id} · {environment(f.environment)}
              </Link>
            </article>
          ))}
        <Link to="/compliance">View all findings</Link>
      </section>
      <Terraform data={data} />
      <section className="panel">
        <h2>Environment coverage</h2>
        <div
          className="table-scroll"
          tabIndex={0}
          aria-label="Scrollable governance table"
        >
          <table>
            <thead>
              <tr>
                <th>Environment</th>
                <th>Accounts</th>
                <th>Evidence age limit</th>
                <th>Deployment approval</th>
              </tr>
            </thead>
            <tbody>
              {["production", "pre-production", "testing", "development"].map(
                (env) => (
                  <tr key={env}>
                    <td>{environment(env)}</td>
                    <td>
                      {
                        data.accounts.filter((a) => a.environment === env)
                          .length
                      }
                    </td>
                    <td>
                      {Array.from(
                        new Set(
                          data.controls.map(
                            (control) => control.max_age_hours[env],
                          ),
                        ),
                      )
                        .sort((a, b) => a - b)
                        .join(" / ")}{" "}
                      hours by control
                    </td>
                    <td>{approvalIntent(data, env)}</td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
        <p>
          All production data publication additionally requires the real GitHub
          Environment approval.
        </p>
      </section>
    </>
  );
}
function Terraform({ data }: { data: ResourceData }) {
  return (
    <section className="panel">
      <h2>Terraform governance validation</h2>
      {data.terraform_validation ? (
        <>
          <Badge status="succeeded" />
          <p>
            Real provider-free Terraform fmt, init, validate and plan; complete
            account/control assignment parity verified before publication.
          </p>
          <p>
            No AWS resources provisioned. Terraform expresses desired
            configuration; the Python engine evaluates synthetic observations.
          </p>
        </>
      ) : (
        <p>
          Not run for this local fixture. CI attaches a verified Terraform plan
          receipt to published data.
        </p>
      )}
    </section>
  );
}
function Accounts({ data, path }: { data: ResourceData; path: string }) {
  const account = data.accounts.find((a) => path === `/accounts/${a.id}`);
  if (path !== "/accounts")
    return account ? (
      <>
        <section className="panel">
          <Link to="/accounts">← All accounts</Link>
          <h2>{account.name}</h2>
          <p>
            {account.id} · {environment(account.environment)} · {account.ou_id}
          </p>
          <Badge status={account.status} />
          <p>
            Lifecycle: {account.lifecycle_status}. No real AWS account is
            represented.
          </p>
        </section>
        <Resources
          data={{
            ...data,
            resources: data.resources.filter(
              (r) => r.account_id === account.id,
            ),
          }}
        />
      </>
    ) : (
      <p role="alert">Account not found.</p>
    );
  return <Inventory data={data} />;
}
function Inventory({ data }: { data: ResourceData }) {
  const [search, setSearch] = useState("");
  const [env, setEnv] = useState("");
  const [status, setStatus] = useState("");
  const [requestedPage, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const rows = data.accounts.filter(
    (a) =>
      `${a.name} ${a.id}`.toLowerCase().includes(search.toLowerCase()) &&
      (!env || a.environment === env) &&
      (!status || a.status === status),
  );
  const page = Math.min(
    requestedPage,
    Math.max(0, Math.ceil(rows.length / pageSize) - 1),
  );
  return (
    <section className="panel">
      <Filters
        search={search}
        env={env}
        status={status}
        update={(key, value) => {
          ({ search: setSearch, env: setEnv, status: setStatus })[key](value);
          setPage(0);
        }}
      />
      <div
        className="table-scroll"
        tabIndex={0}
        aria-label="Scrollable governance table"
      >
        <table>
          <thead>
            <tr>
              <th>Account</th>
              <th>Environment / OU</th>
              <th>Lifecycle</th>
              <th>Resources</th>
              <th>Compliance</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(page * pageSize, (page + 1) * pageSize).map((a) => (
              <tr key={a.id}>
                <td>
                  <Link to={`/accounts/${a.id}`}>{a.name}</Link>
                  <small>{a.id}</small>
                </td>
                <td>
                  {environment(a.environment)}
                  <small>{a.ou_id}</small>
                </td>
                <td>{a.lifecycle_status}</td>
                <td>{a.resource_count}</td>
                <td>
                  <Badge status={a.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows.length && <p>No accounts match these filters.</p>}
      <Pagination
        count={rows.length}
        noun="accounts"
        page={page}
        pageSize={pageSize}
        setPage={setPage}
        setPageSize={setPageSize}
      />
    </section>
  );
}
function Pagination({
  count,
  noun,
  page,
  pageSize,
  setPage,
  setPageSize,
}: {
  count: number;
  noun: string;
  page: number;
  pageSize: number;
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
}) {
  const last = Math.max(0, Math.ceil(count / pageSize) - 1);
  return (
    <div className="resource-pagination">
      <label>
        Rows per page{" "}
        <select
          value={pageSize}
          onChange={(e) => {
            setPageSize(Number(e.target.value));
            setPage(0);
          }}
        >
          {[5, 10, 25, 50].map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
      </label>
      <button disabled={!page} onClick={() => setPage(0)}>
        First
      </button>
      <button disabled={!page} onClick={() => setPage(page - 1)}>
        Previous
      </button>
      <span>
        {count} {noun} · Page {page + 1} of {last + 1}
      </span>
      <button disabled={page === last} onClick={() => setPage(page + 1)}>
        Next
      </button>
      <button disabled={page === last} onClick={() => setPage(last)}>
        Last
      </button>
    </div>
  );
}
function Filters({
  search,
  env,
  status,
  update,
}: {
  search: string;
  env: string;
  status: string;
  update: (key: "search" | "env" | "status", value: string) => void;
}) {
  return (
    <div className="resource-filters">
      <label>
        Search
        <input
          value={search}
          onChange={(e) => update("search", e.target.value)}
        />
      </label>
      <label>
        Environment
        <select value={env} onChange={(e) => update("env", e.target.value)}>
          <option value="">All environments</option>
          {["production", "pre-production", "testing", "development"].map(
            (x) => (
              <option key={x} value={x}>
                {environment(x)}
              </option>
            ),
          )}
        </select>
      </label>
      <label>
        Compliance status
        <select
          value={status}
          onChange={(e) => update("status", e.target.value)}
        >
          <option value="">All statuses</option>
          {["compliant", "noncompliant", "unknown", "stale"].map((x) => (
            <option key={x} value={x}>
              {x}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
function Resources({ data }: { data: ResourceData }) {
  const [search, setSearch] = useState("");
  const [env, setEnv] = useState("");
  const [status, setStatus] = useState("");
  const [requestedPage, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const rows = data.resources.filter(
    (r) =>
      `${r.name} ${r.id} ${r.account_id} ${r.finding.control}`
        .toLowerCase()
        .includes(search.toLowerCase()) &&
      (!env || r.environment === env) &&
      (!status || r.status === status),
  );
  const page = Math.min(
    requestedPage,
    Math.max(0, Math.ceil(rows.length / pageSize) - 1),
  );
  return (
    <section className="panel">
      <p>
        Desired state comes from central controls. Observed state is synthetic
        configuration; differences represent simulated drift.
      </p>
      <Filters
        search={search}
        env={env}
        status={status}
        update={(key, value) => {
          ({ search: setSearch, env: setEnv, status: setStatus })[key](value);
          setPage(0);
        }}
      />
      <div
        className="table-scroll"
        tabIndex={0}
        aria-label="Scrollable governance table"
      >
        <table>
          <thead>
            <tr>
              <th>Resource / account</th>
              <th>Control</th>
              <th>Desired</th>
              <th>Observed</th>
              <th>Evidence</th>
              <th>Result / reason</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(page * pageSize, (page + 1) * pageSize).map((r) => (
              <tr key={r.id}>
                <td>
                  <strong>{r.name}</strong>
                  <small>
                    {r.id} · {r.resource_type}
                  </small>
                  <Link to={`/accounts/${r.account_id}`}>{r.account_id}</Link>
                  <small>{environment(r.environment)}</small>
                </td>
                <td>{r.finding.control}</td>
                <td>{readable(r.finding.expected)}</td>
                <td>{readable(r.finding.observed)}</td>
                <td>
                  {r.observed_at}
                  <small>
                    Maximum age:{" "}
                    {
                      data.controls.find(
                        (control) => control.id === r.finding.control_id,
                      )?.max_age_hours[r.environment]
                    }{" "}
                    hours
                  </small>
                </td>
                <td>
                  <Badge status={r.status} />
                  <p>{r.finding.reason}</p>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows.length && <p>No resources match these filters.</p>}
      <Pagination
        count={rows.length}
        noun="resources"
        page={page}
        pageSize={pageSize}
        setPage={setPage}
        setPageSize={setPageSize}
      />
    </section>
  );
}
function Compliance({ data }: { data: ResourceData }) {
  const [env, setEnv] = useState("");
  const findings = data.findings.filter(
    (finding) => !env || finding.environment === env,
  );
  const statuses = ["compliant", "noncompliant", "unknown", "stale"] as const;
  const count = (rows: typeof findings, status: (typeof statuses)[number]) =>
    rows.filter((finding) => finding.status === status).length;
  return (
    <section className="panel">
      <h2>Compliance by governance control</h2>
      <p>
        Evaluated synthetic evidence grouped by central control. Missing and
        stale evidence are not counted as compliant. These results do not
        represent live AWS Config or Security Hub collection.
      </p>
      <label>
        Environment
        <select value={env} onChange={(event) => setEnv(event.target.value)}>
          <option value="">All environments</option>
          {["production", "pre-production", "testing", "development"].map(
            (value) => (
              <option key={value} value={value}>
                {environment(value)}
              </option>
            ),
          )}
        </select>
      </label>
      <p>{findings.length} synthetic control evaluations in this view.</p>
      <div
        className="table-scroll"
        tabIndex={0}
        aria-label="Compliance by control"
      >
        <table>
          <thead>
            <tr>
              <th>Governance control</th>
              <th>Total</th>
              <th>Compliant</th>
              <th>Noncompliant</th>
              <th>Unknown</th>
              <th>Stale</th>
            </tr>
          </thead>
          <tbody>
            {data.controls.map((control) => {
              const rows = findings.filter(
                (finding) => finding.control_id === control.id,
              );
              return (
                <tr key={control.id}>
                  <td>
                    <strong>{control.name}</strong>
                    <small>{control.reason}</small>
                  </td>
                  <td>{rows.length}</td>
                  {statuses.map((status) => (
                    <td key={status}>{count(rows, status)}</td>
                  ))}
                </tr>
              );
            })}
            <tr>
              <th scope="row">All controls</th>
              <td>{findings.length}</td>
              {statuses.map((status) => (
                <td key={status}>{count(findings, status)}</td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <p>
        To investigate individual desired and observed values, open{" "}
        <Link to="/resources">Resources &amp; drift</Link>. Governance exceptions
        are tracked separately and do not change a failed control into a passing
        result.
      </p>
    </section>
  );
}
function Activity({ data }: { data: ResourceData }) {
  return (
    <>
      <Terraform data={data} />
      <section className="panel">
        <h2>Approved publication history</h2>
        <p>
          Real GitHub approval and data publication. These are synthetic
          governance results, not Terraform apply executions or AWS resource
          remediation.
        </p>
        {!data.activity.length && (
          <p>No protected publications recorded for this local fixture.</p>
        )}
        {data.activity.map((event) => (
          <article className="resource-issue" key={event.operation}>
            <h3>{event.published_at}</h3>
            <p>
              Published by {event.actor} · Source commit{" "}
              {event.source_commit.slice(0, 12)}
            </p>
            <details open={event.changes.length <= 5}>
              <summary>{event.changes.length} resource changes</summary>
              {event.changes.map((change) => (
                <p key={change.resource_id}>
                  <strong>{change.resource_name}</strong>:{" "}
                  {change.before ?? "New resource"} →{" "}
                  {change.after ?? "Removed"} · {readable(change.old_value)} →{" "}
                  {readable(change.new_value)}
                  <br />
                  {change.reason}
                </p>
              ))}
            </details>
          </article>
        ))}
      </section>
      <AccountOperations exceptions={false} />
    </>
  );
}

function AccountOperations({ exceptions }: { exceptions: boolean }) {
  const query = useQuery({
    queryKey: ["account-operations", exceptions],
    queryFn: ({ signal }) => accountRecords(exceptions, signal),
    retry: false,
  });
  return (
    <section className="panel">
      <h2>
        {exceptions
          ? "Account-governance exceptions"
          : "Historical simulated account distribution"}
      </h2>
      <p>
        Existing account-governance records, separate from the resource
        observations above. No real AFT or account deployments occurred.
        Exceptions do not exempt the resource controls.
      </p>
      {query.isPending ? (
        <p role="status">Loading account records…</p>
      ) : query.isError ? (
        <p role="alert">
          Account records unavailable. Resource results have not been changed.
        </p>
      ) : (
        query.data.data.map((record) =>
          "exception" in record ? (
            <article className="resource-issue" key={record.exception.id}>
              <h3>
                {record.exception.account_id} · {record.exception.control_id}
              </h3>
              <Badge status={record.expiration_state.state} />
              <p>{record.exception.rationale}</p>
              <p>
                Owner: {record.exception.owner} · Approver:{" "}
                {record.exception.approver ?? "Not approved"} · Expires:{" "}
                {record.exception.expires_at}
              </p>
              <p>The underlying compliance violation remains visible.</p>
            </article>
          ) : (
            <article className="resource-issue" key={record.id}>
              <h3>
                {record.account_id} · {record.tool}
              </h3>
              <Badge status={record.status} />
              <p>
                Desired: {record.desired_revision} · Observed:{" "}
                {record.observed_revision ?? "Unknown"}
              </p>
              {record.failure_reason && <p>{record.failure_reason}</p>}
            </article>
          ),
        )
      )}
    </section>
  );
}
