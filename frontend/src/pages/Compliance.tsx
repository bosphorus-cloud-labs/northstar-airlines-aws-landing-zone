import { Info } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { useDataset } from "../api/client";
import {
  Badge,
  Evidence,
  PageHeader,
  PaginatedTable,
  Panel,
  QueryGate,
  Select,
} from "../components/ui";
import {
  accountName,
  controlNames,
  environments,
  label,
  statuses,
} from "../format";

export function Compliance() {
  const query = useDataset();
  const [params, setParams] = useSearchParams();
  const value = (key: string) => params.get(key) ?? "";
  const set = (key: string, next: string) => {
    const p = new URLSearchParams(params);
    if (next) p.set(key, next);
    else p.delete(key);
    setParams(p, { replace: true });
  };
  return (
    <>
      <PageHeader
        title="Policy compliance"
        description="Inspect individual control results and the evidence behind every assessment."
      />
      <div className="info-strip">
        <Info size={17} />
        <p>
          <strong>Evidence, not assumptions.</strong> Missing evidence is
          unknown; expired evidence is stale. Exceptions never change a failed
          result to compliant.
        </p>
      </div>
      <QueryGate query={query}>
        {(data) => {
          const rows = data.findings.filter(
            (f) =>
              (!value("status") || f.status === value("status")) &&
              (!value("control_id") || f.control_id === value("control_id")) &&
              (!value("account_id") || f.account_id === value("account_id")) &&
              (!value("environment") ||
                data.accounts.find((a) => a.account.id === f.account_id)
                  ?.account.environment === value("environment")),
          );
          return (
            <Panel
              title="Control findings"
              action={
                <span className="subtle-tag">
                  {data.summary.finding_count} total evaluations
                </span>
              }
            >
              <div className="filters wrap">
                <Select
                  title="Environment"
                  value={value("environment")}
                  onChange={(v) => set("environment", v)}
                  options={environments}
                  all="All environments"
                />
                <Select
                  title="Control"
                  value={value("control_id")}
                  onChange={(v) => set("control_id", v)}
                  options={Object.keys(controlNames)}
                  all="All controls"
                />
                <Select
                  title="Compliance status"
                  value={value("status")}
                  onChange={(v) => set("status", v)}
                  options={statuses}
                  all="All statuses"
                />
                <Select
                  title="Account"
                  value={value("account_id")}
                  onChange={(v) => set("account_id", v)}
                  options={data.accounts.map((a) => a.account.id)}
                  all="All accounts"
                />
              </div>
              <PaginatedTable
                key={params.toString()}
                rows={rows}
                noun="findings"
                columns={[
                  "Control / Account",
                  "Environment",
                  "Result",
                  "Evidence freshness",
                  "Exceptions",
                ]}
                render={(f) => (
                  <tr key={f.id}>
                    <td>
                      <strong>{controlNames[f.control_id]}</strong>
                      <Link
                        className="secondary-link"
                        to={`/accounts/${f.account_id}`}
                      >
                        {accountName(data.accounts, f.account_id)}
                        <span className="mono"> · {f.account_id}</span>
                      </Link>
                    </td>
                    <td>
                      {label(
                        data.accounts.find((a) => a.account.id === f.account_id)
                          ?.account.environment ?? "Unassigned",
                      )}
                    </td>
                    <td>
                      <Badge status={f.status} />
                    </td>
                    <td>
                      <Evidence reason={f.reason} />
                      <small className="mono">
                        {f.evidence_id ?? "No observation"}
                      </small>
                    </td>
                    <td>
                      {f.exceptions.length ? (
                        f.exceptions.map((e) => (
                          <Link
                            key={e.id}
                            className="exception-reference"
                            to="/exceptions"
                          >
                            {e.id}
                            <small>{label(e.state)} · result unchanged</small>
                          </Link>
                        ))
                      ) : (
                        <span className="muted">No exception</span>
                      )}
                    </td>
                  </tr>
                )}
              />
              <div className="status-explanations">
                <span>
                  <b>Compliant</b> Fresh matching evidence
                </span>
                <span>
                  <b>Noncompliant</b> Fresh failing evidence
                </span>
                <span>
                  <b>Unknown</b> Insufficient valid evidence
                </span>
                <span>
                  <b>Stale</b> Evidence beyond allowed age
                </span>
              </div>
            </Panel>
          );
        }}
      </QueryGate>
    </>
  );
}
