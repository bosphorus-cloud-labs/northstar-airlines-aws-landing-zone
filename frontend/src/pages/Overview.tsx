import {
  ArrowDownRight,
  ArrowUpRight,
  CircleHelp,
  Layers3,
  ShieldCheck,
  ShieldX,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useDataset, type Dataset, type Status } from "../api/client";
import { Badge, PageHeader, Panel, QueryGate } from "../components/ui";
import { accountName, date, label } from "../format";

const colors: Record<Status, string> = {
  compliant: "#168b75",
  noncompliant: "#d66a59",
  unknown: "#96a4af",
  stale: "#d7a342",
};
function OverviewContent({ data }: { data: Dataset }) {
  const { summary } = data;
  const states = ["compliant", "noncompliant", "unknown", "stale"] as const;
  let current = 0;
  const segments = states
    .map((status) => {
      const start = current;
      current += summary.account_count
        ? (summary.account_counts[status] / summary.account_count) * 100
        : 0;
      return `${colors[status]} ${start}% ${current}%`;
    })
    .join(", ");
  const recent = [...data.deployments]
    .sort(
      (a, b) =>
        b.started_at.localeCompare(a.started_at) || b.id.localeCompare(a.id),
    )
    .slice(0, 4);
  const failures = data.deployments.filter((d) => d.status === "failed").length;
  const drifted = data.drift.filter((d) => d.status === "drifted").length;
  return (
    <>
      <div className="metrics-grid">
        <Metric
          title="Accounts in scope"
          value={summary.account_count}
          icon={<Layers3 size={19} />}
          foot={`Across ${Object.keys(summary.environment_counts).length} environment profiles`}
        />
        <Metric
          title="Compliant accounts"
          value={summary.account_counts.compliant}
          icon={<ShieldCheck size={19} />}
          tone="green"
          foot="All evaluated controls passing"
        />
        <Metric
          title="Noncompliant accounts"
          value={summary.account_counts.noncompliant}
          icon={<ShieldX size={19} />}
          tone="red"
          foot="Underlying violations stay visible"
        />
        <Metric
          title="Evidence gaps"
          value={summary.account_counts.unknown + summary.account_counts.stale}
          icon={<CircleHelp size={19} />}
          tone="amber"
          foot={`${summary.account_counts.unknown} unknown · ${summary.account_counts.stale} stale accounts`}
        />
      </div>
      <div className="overview-grid">
        <Panel
          title="Account compliance posture"
          eyebrow="FLEET HEALTH"
          action={
            <Link className="text-link" to="/accounts">
              View accounts <ArrowUpRight size={15} />
            </Link>
          }
        >
          <div className="posture-content">
            <div
              className="donut"
              role="img"
              aria-label={states
                .map((s) => `${summary.account_counts[s]} ${s} accounts`)
                .join(", ")}
              style={{
                background: summary.account_count
                  ? `conic-gradient(${segments})`
                  : "#e5e9e9",
              }}
            >
              <div>
                <strong>
                  {summary.account_counts.compliant}
                  <span> / {summary.account_count}</span>
                </strong>
                <small>compliant accounts</small>
              </div>
            </div>
            <div className="legend">
              {states.map((status) => (
                <div key={status}>
                  <span
                    className="legend-dot"
                    style={{ background: colors[status] }}
                  />
                  <span>{label(status)}</span>
                  <strong>{summary.account_counts[status]}</strong>
                </div>
              ))}
            </div>
          </div>
          <div className="panel-footnote">
            <CircleHelp size={14} />
            Unknown and stale evidence never count as compliant.
          </div>
        </Panel>
        <Panel
          title="Environment distribution"
          eyebrow="ACCOUNT LANDSCAPE"
          action={
            <span className="subtle-tag">{summary.account_count} accounts</span>
          }
        >
          <div className="environment-bars">
            {Object.entries(summary.environment_counts).map(
              ([environment, count]) => (
                <div className="environment-row" key={environment}>
                  <div>
                    <span>{label(environment)}</span>
                    <strong>
                      {count} <small>accounts</small>
                    </strong>
                  </div>
                  <div className="bar-track">
                    <span
                      style={{
                        width: `${summary.account_count ? (count / summary.account_count) * 100 : 0}%`,
                      }}
                    />
                  </div>
                </div>
              ),
            )}
          </div>
          <div className="panel-footnote">
            Each environment inherits the organization-wide baseline.
          </div>
        </Panel>
      </div>
      <Panel
        title="Control evaluation coverage"
        action={
          <Link className="text-link" to="/compliance">
            Explore findings <ArrowUpRight size={15} />
          </Link>
        }
      >
        <div className="control-coverage">
          <div className="coverage-total">
            <strong>{summary.finding_count}</strong>
            <span>control findings</span>
          </div>
          <div className="coverage-body">
            <div
              className="stacked-bar"
              role="img"
              aria-label="Control results distribution"
            >
              {states.map((status) => (
                <span
                  key={status}
                  style={{
                    flex: summary.finding_counts[status],
                    background: colors[status],
                  }}
                />
              ))}
            </div>
            <div className="coverage-legend">
              {states.map((status) => (
                <span key={status}>
                  <i style={{ background: colors[status] }} />
                  <strong>{summary.finding_counts[status]}</strong>{" "}
                  {label(status)}
                </span>
              ))}
            </div>
          </div>
        </div>
      </Panel>
      <div className="overview-bottom">
        <Panel
          title="Recent deployments"
          eyebrow="SIMULATED EXECUTIONS"
          action={
            <Link className="text-link" to="/deployments">
              View history <ArrowUpRight size={15} />
            </Link>
          }
        >
          <p className="table-hint">Scroll horizontally to view all columns.</p>
          <div
            className="table-scroll"
            tabIndex={0}
            aria-label="Recent deployments table; scroll horizontally on small screens"
          >
            <table>
              <thead>
                <tr>
                  <th scope="col">Account</th>
                  <th scope="col">Pipeline</th>
                  <th scope="col">Status</th>
                  <th scope="col">Started (UTC)</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <Link
                        className="account-link"
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
                    </td>
                    <td>
                      <Badge status={d.status} />
                    </td>
                    <td className="muted">{date(d.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!recent.length && (
              <p className="inline-empty">No deployment history recorded.</p>
            )}
          </div>
        </Panel>
        <Panel title="Governance attention" eyebrow="REVIEW QUEUE">
          <div className="attention-list">
            <Link to="/compliance?status=noncompliant">
              <span className="attention-icon red">
                <ShieldX size={18} />
              </span>
              <div>
                <strong>Policy violations</strong>
                <small>Failed control evaluations</small>
              </div>
              <b>{summary.finding_counts.noncompliant}</b>
              <ArrowUpRight size={15} />
            </Link>
            <Link to="/deployments?status=failed">
              <span className="attention-icon amber">
                <ArrowDownRight size={18} />
              </span>
              <div>
                <strong>Deployment failures</strong>
                <small>Simulated pipeline failures</small>
              </div>
              <b>{failures}</b>
              <ArrowUpRight size={15} />
            </Link>
            <Link to="/drift">
              <span className="attention-icon blue">
                <Layers3 size={18} />
              </span>
              <div>
                <strong>Configuration drift</strong>
                <small>Desired and observed differ</small>
              </div>
              <b>{drifted}</b>
              <ArrowUpRight size={15} />
            </Link>
          </div>
          <p className="quiet-note">
            Read-only visibility. This console does not execute changes or
            remediation.
          </p>
        </Panel>
      </div>
    </>
  );
}
function Metric({
  title,
  value,
  foot,
  icon,
  tone = "",
}: {
  title: string;
  value: number;
  foot: string;
  icon: React.ReactNode;
  tone?: string;
}) {
  return (
    <article className={`metric ${tone}`}>
      <div>
        <span>{title}</span>
        <i>{icon}</i>
      </div>
      <strong>{value}</strong>
      <p>{foot}</p>
    </article>
  );
}
export function Overview() {
  const query = useDataset();
  return (
    <>
      <PageHeader
        title="Governance overview"
        description="One clear view of account posture, policy evidence, and fleet operations."
      />
      <QueryGate query={query}>
        {(data) => <OverviewContent data={data} />}
      </QueryGate>
    </>
  );
}
