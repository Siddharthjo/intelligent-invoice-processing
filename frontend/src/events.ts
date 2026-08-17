import type { User } from "./api";

export const LOGIN_EVENT = "ledger:login";

export type LoginEvent = CustomEvent<User>;

declare global {
  interface WindowEventMap {
    [LOGIN_EVENT]: LoginEvent;
  }
}
