import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Check,
  CircleHelp,
  Clock3,
  LoaderCircle,
  RefreshCw,
  Search,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import { controlNames, label } from "../format";

export function Badge({ status }: { status: string }) {
  const Icon = [
    "compliant",
    "succeeded",
    "in-sync",
    "active",
    "approved",
  ].includes(status)
    ? Check
    : ["noncompliant", "failed", "drifted", "rejected"].includes(status)
      ? AlertCircle
      : ["stale", "expired", "pending", "onboarding"].includes(status)
        ? Clock3
        : CircleHelp;
  return (
    <span className={`badge status-${status}`}>
      <Icon size={12} aria-hidden="true" />
      {label(status)}
    </span>
  );
}
export function Panel({
  title,
  eyebrow,
  action,
  children,
  className = "",
}: {
  title: string;
  eyebrow?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-header">
        <div>
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function PageHeader({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="page-header">
      <div>
        <p className="eyebrow">NORTHSTAR GOVERNANCE CONSOLE</p>
        <h1 tabIndex={-1}>{title}</h1>
        <p>{description}</p>
      </div>
      <span className="mode-label">
        <span />
        Read-only workspace
      </span>
    </div>
  );
}
export function QueryGate<T>({
  query,
  children,
}: {
  query: UseQueryResult<T, Error>;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending)
    return (
      <div className="loading-state" role="status">
        <LoaderCircle className="spin" size={25} />
        <strong>Loading governance evidence</strong>
        <p>Reading the reference snapshot from the API…</p>
        <div className="skeleton-grid">
          {[0, 1, 2].map((n) => (
            <i key={n} />
          ))}
        </div>
      </div>
    );
  if (query.isError)
    return (
      <div className="error-state" role="alert">
        <AlertCircle size={30} />
        <h2>Governance data is unavailable</h2>
        <p>
          {query.error instanceof ApiError
            ? query.error.message
            : "The API response could not be displayed. Check the backend contract and try again."}
        </p>
        <button className="button primary" onClick={() => void query.refetch()}>
          <RefreshCw size={15} />
          Try again
        </button>
      </div>
    );
  return (
    <>
      {query.isFetching && (
        <p className="refresh-note" role="status">
          Refreshing API snapshot…
        </p>
      )}
      {children(query.data)}
    </>
  );
}
export function Empty({
  message = "No records match your filters.",
}: {
  message?: string;
}) {
  return (
    <div className="empty-state">
      <Search size={24} />
      <h3>No results found</h3>
      <p>{message}</p>
    </div>
  );
}
export function Select({
  title,
  value,
  onChange,
  options,
  all = "All",
}: {
  title: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly string[];
  all?: string;
}) {
  return (
    <label className="filter">
      <span>{title}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{all}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {controlNames[option] ?? label(option)}
          </option>
        ))}
      </select>
    </label>
  );
}
export function SearchInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="search-input">
      <Search size={17} />
      <span className="sr-only">Search accounts</span>
      <input
        type="search"
        placeholder="Search accounts or identifiers…"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
export function PaginatedTable<T>({
  rows,
  columns,
  render,
  noun = "records",
}: {
  rows: T[];
  columns: string[];
  render: (row: T, index: number) => ReactNode;
  noun?: string;
}) {
  const [page, setPage] = useState(0);
  const pageSize = 5;
  const effectivePage = Math.min(
    page,
    Math.max(0, Math.ceil(rows.length / pageSize) - 1),
  );
  const start = effectivePage * pageSize;
  return (
    <>
      {rows.length > 0 && (
        <p className="table-hint">Scroll horizontally to view all columns.</p>
      )}
      {rows.length ? (
        <div
          className="table-scroll"
          tabIndex={0}
          aria-label={`${noun} table; scroll horizontally on small screens`}
        >
          <table>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th scope="col" key={column}>
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>{rows.slice(start, start + pageSize).map(render)}</tbody>
          </table>
        </div>
      ) : (
        <Empty />
      )}
      <div className="pagination">
        <span>
          {rows.length
            ? `${start + 1}–${Math.min(start + pageSize, rows.length)}`
            : "0"}{" "}
          of {rows.length} {noun}
        </span>
        <div>
          <button
            className="icon-button"
            aria-label="Previous page"
            disabled={effectivePage === 0}
            onClick={() => setPage(effectivePage - 1)}
          >
            <ArrowLeft size={16} />
          </button>
          <span>
            Page {effectivePage + 1} of{" "}
            {Math.max(1, Math.ceil(rows.length / pageSize))}
          </span>
          <button
            className="icon-button"
            aria-label="Next page"
            disabled={start + pageSize >= rows.length}
            onClick={() => setPage(effectivePage + 1)}
          >
            <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </>
  );
}

export function Evidence({
  reason,
  observedAt,
}: {
  reason: string;
  observedAt?: string;
}) {
  const explanations: Record<string, string> = {
    match: "Fresh at evaluation",
    mismatch: "Fresh at evaluation",
    "missing-evidence": "No evidence recorded",
    "stale-evidence": "Evidence expired",
    "future-evidence": "Future observation only",
    "revision-mismatch": "Different policy revision",
  };
  return (
    <span
      className={`freshness ${reason === "stale-evidence" ? "warning-text" : ""}`}
    >
      <Clock3 size={13} />
      {explanations[reason] ?? label(reason)}
      {observedAt && (
        <small className="evidence-timestamp">
          {new Date(observedAt)
            .toISOString()
            .replace("T", " ")
            .replace(".000Z", " UTC")}
        </small>
      )}
    </span>
  );
}
