import type { Dataset } from "../api/client";
import { useSelection } from "../api/selection";
import { Panel } from "./ui";

export function RolloutHistory({ data }: { data: Dataset }) {
  const selection = useSelection();
  const latest = [...data.deployments].sort(
    (a, b) =>
      b.started_at.localeCompare(a.started_at) || b.id.localeCompare(a.id),
  )[0];
  const attempts = latest
    ? data.deployments.filter((d) => d.correlation_id === latest.correlation_id)
    : [];
  const targets = [...new Set(attempts.map((d) => d.account_id))];
  const journal = "journal" in data.summary ? data.summary.journal : [];
  const approval = journal.find((e) => e.action === "policy.approved");
  const deferred = new Set(
    journal
      .filter((e) => e.action === "deployment.deferred")
      .map((e) => e.account_id),
  );
  const completed = journal.some((e) => e.action === "rollout.completed");
  return (
    <Panel
      title="Governance rollout history"
      action={<span className="simulation-mini">SIMULATED OPERATIONS</span>}
    >
      <div className="rollout-operation-summary">
        <strong>Policy revision {selection.policy_version}</strong>
        <span>
          Latest recorded run:{" "}
          <code>{latest?.correlation_id ?? "No execution recorded"}</code>
        </span>
        <span>
          {targets.length} targeted accounts · {attempts.length} attempts ·{" "}
          {Math.max(0, attempts.length - targets.length)} retries retained ·{" "}
          {attempts.filter((d) => d.status === "failed").length} failed attempts
        </span>
        <span>
          Approval:{" "}
          {approval
            ? `${approval.actor} at ${approval.at}`
            : "Not recorded in the baseline history"}
        </span>
        <span>
          Distribution:{" "}
          {completed
            ? `completed with ${deferred.size} inactive accounts deferred`
            : (latest?.status ?? "not observed")}
        </span>
        <p>
          Configuration distribution is separate from compliance evidence:{" "}
          {data.summary.finding_counts.noncompliant} noncompliant,{" "}
          {data.summary.finding_counts.unknown} unknown and{" "}
          {data.summary.finding_counts.stale} stale findings remain in this
          evaluation.
        </p>
      </div>
      {targets.length > 0 && (
        <details>
          <summary>Target accounts</summary>
          <p className="mono">{targets.join(", ")}</p>
        </details>
      )}
      {journal.length > 0 && (
        <details className="operation-journal">
          <summary>
            Approval, deployment stages, failure/retry and final outcomes
          </summary>
          <ol>
            {journal.map((event) => (
              <li key={event.sequence}>
                <strong>{event.action.replaceAll(".", " ")}</strong> ·{" "}
                {event.account_id ?? "fleet"} · <time>{event.at}</time>
                <p>{event.detail}</p>
              </li>
            ))}
          </ol>
        </details>
      )}
      <p className="panel-footnote">
        These are simulated policy operations. No AWS execution or automatic
        remediation is performed by this read-only console.
      </p>
    </Panel>
  );
}
