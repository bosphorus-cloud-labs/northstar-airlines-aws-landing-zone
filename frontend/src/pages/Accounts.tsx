import { ArrowLeft, ArrowUpRight, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAccount, useDataset } from "../api/client";
import {
  Badge,
  Evidence,
  PageHeader,
  PaginatedTable,
  Panel,
  QueryGate,
  SearchInput,
  Select,
} from "../components/ui";
import { controlNames, date, environments, label, statuses } from "../format";

export function Accounts() {
  const query = useDataset();
  const [search, setSearch] = useState("");
  const [environment, setEnvironment] = useState("");
  const [status, setStatus] = useState("");
  return (
    <>
      <PageHeader
        title="Account inventory"
        description="Explore the synthetic fleet and its assigned governance baselines."
      />
      <QueryGate query={query}>
        {(data) => {
          const filtered = data.accounts.filter(
            ({ account, compliance }) =>
              (!environment || account.environment === environment) &&
              (!status || compliance.status === status) &&
              `${account.name} ${account.id} ${account.ou_id}`
                .toLowerCase()
                .includes(search.toLowerCase().trim()),
          );
          return (
            <Panel
              title="Fleet accounts"
              action={
                <span className="subtle-tag">
                  {data.accounts.length} synthetic accounts
                </span>
              }
            >
              <div className="filters">
                <SearchInput value={search} onChange={setSearch} />
                <Select
                  title="Environment"
                  value={environment}
                  onChange={setEnvironment}
                  options={environments}
                  all="All environments"
                />
                <Select
                  title="Compliance status"
                  value={status}
                  onChange={setStatus}
                  options={statuses}
                  all="All statuses"
                />
              </div>
              <PaginatedTable
                key={`${search}|${environment}|${status}`}
                noun="accounts"
                rows={filtered}
                columns={[
                  "Account",
                  "Environment / OU",
                  "Lifecycle",
                  "Policy revision",
                  "Compliance",
                  "Details",
                ]}
                render={({ account, compliance }) => (
                  <tr key={account.id}>
                    <td>
                      <Link
                        className="account-link"
                        to={`/accounts/${account.id}`}
                      >
                        {account.name}
                      </Link>
                      <small className="mono">{account.id}</small>
                    </td>
                    <td>
                      <span>{label(account.environment)}</span>
                      <small className="mono">{account.ou_id}</small>
                    </td>
                    <td>
                      <Badge status={account.lifecycle_status} />
                    </td>
                    <td>
                      <span className="version">
                        v{account.desired_policy_version}
                      </span>
                    </td>
                    <td>
                      <Badge status={compliance.status} />
                    </td>
                    <td>
                      <Link
                        className="row-link"
                        aria-label={`View ${account.id}`}
                        to={`/accounts/${account.id}`}
                      >
                        <ArrowUpRight size={18} />
                      </Link>
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
export function AccountDetail() {
  const { accountId = "" } = useParams();
  const query = useAccount(accountId);
  return (
    <>
      <Link className="back-link" to="/accounts">
        <ArrowLeft size={15} />
        Account inventory
      </Link>
      <PageHeader
        title="Account details"
        description="Desired policy, evaluated evidence, and exceptions for a single synthetic account."
      />
      <QueryGate query={query}>
        {(response) => {
          const { account, compliance, ou, findings } = response.data;
          return (
            <>
              <section className="account-summary">
                <div className="account-avatar">NS</div>
                <div>
                  <h2>{account.name}</h2>
                  <span className="mono">{account.id}</span>
                </div>
                <Badge status={compliance.status} />
                <span className="simulation-mini">SIMULATED ACCOUNT</span>
              </section>
              <div className="detail-grid">
                <div>
                  <span>Environment</span>
                  <strong>{label(account.environment)}</strong>
                </div>
                <div>
                  <span>Organizational unit</span>
                  <strong className="mono">{ou.id}</strong>
                </div>
                <div>
                  <span>Desired policy revision</span>
                  <strong>v{account.desired_policy_version}</strong>
                </div>
                <div>
                  <span>Lifecycle / Created</span>
                  <strong>
                    {label(account.lifecycle_status)} ·{" "}
                    {date(account.created_at)}
                  </strong>
                </div>
              </div>
              <Panel
                title="Control evidence"
                action={
                  <Link
                    className="text-link"
                    to={`/compliance?account_id=${account.id}`}
                  >
                    View compliance <ChevronRight size={15} />
                  </Link>
                }
              >
                <PaginatedTable
                  rows={findings}
                  columns={[
                    "Control",
                    "Desired / Observed",
                    "Result",
                    "Evidence",
                    "Exceptions",
                  ]}
                  render={(finding) => (
                    <tr key={finding.id}>
                      <td>
                        <strong>{controlNames[finding.control_id]}</strong>
                        <small className="mono">{finding.control_id}</small>
                      </td>
                      <td>
                        {String(finding.desired_value)} /{" "}
                        {finding.observed_value === null
                          ? "Not observed"
                          : String(finding.observed_value)}
                      </td>
                      <td>
                        <Badge status={finding.status} />
                      </td>
                      <td>
                        <Evidence reason={finding.reason} />
                      </td>
                      <td>
                        {finding.exceptions.length ? (
                          finding.exceptions.map((e) => (
                            <Link
                              key={e.id}
                              className="exception-reference"
                              to="/exceptions"
                            >
                              {e.id} · {label(e.state)}
                            </Link>
                          ))
                        ) : (
                          <span className="muted">None</span>
                        )}
                      </td>
                    </tr>
                  )}
                />
              </Panel>
            </>
          );
        }}
      </QueryGate>
    </>
  );
}
