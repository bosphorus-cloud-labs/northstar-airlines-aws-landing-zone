import { createContext, useContext } from "react";
export const Session = createContext<{
  mode: "local" | "cognito";
  signOut?: () => void;
}>({ mode: "local" });
export const useSession = () => useContext(Session);
