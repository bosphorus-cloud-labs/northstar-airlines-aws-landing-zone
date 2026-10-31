import { GitCompareArrows, Info, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useDataset } from "../api/client";
import {
  Badge,
  PageHeader,
  PaginatedTable,
  Panel,
  QueryGate,
  Select,
} from "../components/ui";
import { accountName, controlNames, date, environments } from "../format";

export function Deployments() {
  const query = useDataset();
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const [environment, setEnvironment] = useState("");
  const [tool, setTool] = useState("");
  return (
    <>
      <PageHeader
        title="Deployment history"
        description="Trace simulated Terraform and AFT revisions, outcomes, and failure context."
      />
      <div className="info-strip">
        <Info size={17} />
        <p>
          <strong>Simulated executions only.</strong> These records do not
          represent pipelines that ran against AWS. No deployment actions are
          available.
        </p>
      </div>
      <QueryGate query={query}>
        {(data) => {
          const rows = data.deployments
            .filter(
              (d) =>
                (!status || d.status === status) &&
                (!tool || d.tool === tool) &&
                (!environment ||
                  data.accounts.find((a) => a.account.id === d.account_id)
                    ?.account.environment === environment),
            )
            .sort(
              (a, b) =>
                b.started_at.localeCompare(a.started_at) ||
                b.id.localeCompare(a.id),
            );
          return (
            <Panel
              title="Pipeline executions"
              action={
                <span className="simulation-mini">SIMULATED HISTORY</span>
              }
            >
              <div className="filters">
                <Select
                  title="Environment"
                  value={environment}
                  onChange={setEnvironment}
                  options={environments}
                  all="All environments"
                />
                <Select
                  title="Execution status"
                  value={status}
                  onChange={(v) => setParams(v ? { status: v } : {})}
                  options={["succeeded", "failed", "pending"]}
                  all="All statuses"
                />
                <Select
                  title="Pipeline"
                  value={tool}
                  onChange={setTool}
                  options={["terraform", "aft"]}
                  all="All pipelines"
                />
              </div>
              <PaginatedTable
                key={`${environment}|${status}|${tool}`}
                rows={rows}
                noun="executions"
                columns={[
                  "Execution / Account",
                  "Pipeline",
                  "Desired → Observed revision",
                  "Status",
                  "Started (UTC) / Context",
                ]}
                render={(d) => (
                  <tr key={d.id}>
                    <td>
                      <strong className="mono">{d.id}</strong>
                      <Link
                        className="secondary-link"
                        to={`/accounts/${d.account_id}`}
                      >
                        {accountName(data.accounts, d.account_id)}
                      </Link>
                      <small className="mono">{d.account_id}</small>
                    </td>
                    <td>
                      <span className="tool-label">
                        {d.tool === "aft" ? "AFT" : "Terraform"}
                      </span>
                      <small>Simulated</small>
                    </td>
                    <td>
                      <div className="revision-pair">
                        <code>{d.desired_revision}</code>
                        <span>↓ observed</span>
                        <code
                          className={
                            d.observed_revision !== d.desired_revision
                              ? "warning-text"
                              : ""
                          }
                        >
                          {d.observed_revision ?? "Not observed"}
                        </code>
                      </div>
                    </td>
                    <td>
                      <Badge status={d.status} />
                    </td>
                    <td>
                      {date(d.started_at)}
                      <small
                        className={d.failure_reason ? "failure-reason" : ""}
                      >
                        {d.failure_reason ??
                          (d.completed_at
                            ? `Completed ${date(d.completed_at)}`
                            : "Awaiting completion")}
                      </small>
                      <small className="mono">{d.correlation_id}</small>
                    </td>
                  </tr>
                )}
              />
            </Panel>
          );
        }}
      </QueryGate>
    </>
  );
}
export function Drift() {
  const query = useDataset();
  const [state, setState] = useState("");
  return (
    <>
      <PageHeader
        title="Configuration drift"
        description="Compare desired configuration with the last recorded synthetic observation."
      />
      <div className="info-strip">
        <GitCompareArrows size={18} />
        <p>
          <strong>Observed is not desired.</strong> Drift records are supplied
          simulation snapshots; this console does not scan or remediate AWS
          resources.
        </p>
      </div>
      <QueryGate query={query}>
        {(data) => (
          <Panel
            title="Drift observations"
            action={
              <span className="subtle-tag">{data.drift.length} recorded</span>
            }
          >
            <div className="filters">
              <Select
                title="Drift state"
                value={state}
                onChange={setState}
                options={["drifted", "in-sync", "unknown"]}
                all="All states"
              />
            </div>
            <PaginatedTable
              key={state}
              rows={data.drift.filter((d) => !state || d.status === state)}
              noun="observations"
              columns={[
                "Account / Control",
                "Desired value",
                "Observed value",
                "Revisions",
                "Drift state",
              ]}
              render={(d) => (
                <tr key={d.id}>
                  <td>
                    <Link
                      className="account-link"
                      to={`/accounts/${d.account_id}`}
                    >
                      {accountName(data.accounts, d.account_id)}
                    </Link>
                    <small className="mono">{d.account_id}</small>
                    <span className="control-chip">
                      {controlNames[d.control_id]}
                    </span>
                  </td>
                  <td>
                    <span className="configuration-value">
                      <span className="value-marker desired" />
                      {String(d.desired_value)}
                    </span>
                    <small>Required configuration</small>
                  </td>
                  <td>
                    <span className="configuration-value">
                      <span className="value-marker observed" />
                      {d.observed_value === null
                        ? "Not observed"
                        : String(d.observed_value)}
                    </span>
                    <small>{date(d.observed_at)} UTC</small>
                  </td>
                  <td>
                    <div className="revision-pair">
                      <code>{d.desired_revision}</code>
                      <span>↓ observed</span>
                      <code>{d.observed_revision ?? "Not observed"}</code>
                    </div>
                  </td>
                  <td>
                    <Badge status={d.status} />
                  </td>
                </tr>
              )}
            />
            <div className="panel-footnote">
              Boolean “true” means the safeguard is enabled. Revision
              differences remain visible independently of value comparisons.
            </div>
          </Panel>
        )}
      </QueryGate>
    </>
  );
}
export function Exceptions() {
  const query = useDataset();
  const [state, setState] = useState("");
  const [environment, setEnvironment] = useState("");
  return (
    <>
      <PageHeader
        title="Governance exceptions"
        description="Review risk acceptance, accountable owners, expiry, and the original control findings."
      />
      <div className="info-strip amber-strip">
        <ShieldAlert size={18} />
        <p>
          <strong>An exception is not a passing control.</strong> Approved and
          expired exceptions preserve the underlying violation. This workspace
          cannot grant approvals.
        </p>
      </div>
      <QueryGate query={query}>
        {(data) => {
          const rows = data.exceptions.filter(
            (e) =>
              (!state || e.expiration_state.state === state) &&
              (!environment ||
                data.accounts.find(
                  (a) => a.account.id === e.exception.account_id,
                )?.account.environment === environment),
          );
          return (
            <Panel
              title="Exception register"
              action={
                <span className="subtle-tag">
                  {data.exceptions.length} recorded
                </span>
              }
            >
              <div className="filters">
                <Select
                  title="Expiration state"
                  value={state}
                  onChange={setState}
                  options={[
                    "active",
                    "expired",
                    "pending",
                    "rejected",
                    "not-yet-active",
                  ]}
                  all="All states"
                />
                <Select
                  title="Environment"
                  value={environment}
                  onChange={setEnvironment}
                  options={environments}
                  all="All environments"
                />
              </div>
              <PaginatedTable
                key={`${state}|${environment}`}
                rows={rows}
                noun="exceptions"
                columns={[
                  "Exception / Rationale",
                  "Account / Control",
                  "Owner / Approver",
                  "Approval / Expiration",
                  "Original finding",
                ]}
                render={({ exception: e, expiration_state }) => {
                  const finding = data.findings.find(
                    (f) =>
                      f.account_id === e.account_id &&
                      f.control_id === e.control_id,
                  );
                  return (
                    <tr key={e.id}>
                      <td>
                        <strong className="mono">{e.id}</strong>
                        <small className="exception-reason">
                          {e.rationale}
                        </small>
                      </td>
                      <td>
                        <Link
                          className="account-link"
                          to={`/accounts/${e.account_id}`}
                        >
                          {accountName(data.accounts, e.account_id)}
                        </Link>
                        <small className="mono">{e.account_id}</small>
                        <span className="control-chip">
                          {controlNames[e.control_id]}
                        </span>
                      </td>
                      <td>
                        <strong>{e.owner}</strong>
                        <small>Approver: {e.approver ?? "Not approved"}</small>
                        <small className="mono">
                          {e.approval_reference ?? "No approval reference"}
                        </small>
                      </td>
                      <td>
                        <Badge status={e.status} />
                        <div className="exception-expiry">
                          <Badge status={expiration_state.state} />
                          <small>Expires {date(e.expires_at)} UTC</small>
                        </div>
                      </td>
                      <td>
                        {finding ? (
                          <>
                            <Badge status={finding.status} />
                            <Link
                              className="secondary-link"
                              to={`/compliance?account_id=${e.account_id}&control_id=${e.control_id}`}
                            >
                              Review original finding →
                            </Link>
                          </>
                        ) : (
                          <span className="muted">Finding not available</span>
                        )}
                      </td>
                    </tr>
                  );
                }}
              />
              <div className="panel-footnote">
                {rows.filter((e) => e.expiration_state.state === "pending")
                  .length === 0
                  ? "No pending exceptions in this filtered snapshot."
                  : "Pending requests are not approved risk acceptance."}{" "}
                All records are simulated.
              </div>
            </Panel>
          );
        }}
      </QueryGate>
    </>
  );
}
