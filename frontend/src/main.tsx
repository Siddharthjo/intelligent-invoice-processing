import { createRoot, type Root } from "react-dom/client";
import { StrictMode } from "react";
import { LoginApp } from "./LoginApp";
import { AnalyticsApp } from "./AnalyticsApp";

let loginRoot: Root | null = null;
let analyticsRoot: Root | null = null;

function mountLogin() {
  const el = document.getElementById("login-view");
  if (!el) return;
  // Remount (not reuse) so a fresh, empty form appears every time -- e.g. after
  // logout, the previous username shouldn't linger in a merely re-rendered root.
  loginRoot?.unmount();
  loginRoot = createRoot(el);
  loginRoot.render(
    <StrictMode>
      <LoginApp />
    </StrictMode>,
  );
}

function mountAnalytics() {
  const el = document.getElementById("analytics-view");
  if (!el) return;
  // Remount (not reuse) on every call so a fresh fetch runs each time the view
  // is shown -- mirrors the previous vanilla-JS loadAnalytics()-on-every-show behavior.
  analyticsRoot?.unmount();
  analyticsRoot = createRoot(el);
  analyticsRoot.render(
    <StrictMode>
      <AnalyticsApp />
    </StrictMode>,
  );
}

declare global {
  interface Window {
    LedgerReact: {
      mountLogin: () => void;
      mountAnalytics: () => void;
    };
  }
}

window.LedgerReact = { mountLogin, mountAnalytics };

if (import.meta.env.DEV) {
  mountLogin();
  mountAnalytics();
}
