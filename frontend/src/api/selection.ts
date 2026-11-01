import { createContext, useContext } from "react";
export type Selection = {
  ready?: boolean;
  policy_version: string;
  evaluated_at: string;
  snapshot_id: string | null;
};
export const DEFAULT_SELECTION: Selection = {
  policy_version: "1.0.0",
  evaluated_at: "2026-10-31T12:00:00Z",
  snapshot_id: null,
};
export const SelectionContext = createContext<Selection>(DEFAULT_SELECTION);
export const useSelection = () => useContext(SelectionContext);
