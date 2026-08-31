import { useEffect, useRef, useState } from "react";
import Keycloak from "keycloak-js";

type PortalConfig = {
  ready: boolean;
  keycloak_url: string;
  realm: string;
  client_id: string | null;
  required_roles: string[];
};

type PortalSession = {
  identity: { subject: string; email: string; name: string };
  representations: Array<{
    id: string;
    client_name: string;
    representation_type: string;
    status: string;
    effective_at: string | null;
    expires_at: string | null;
  }>;
  transactions: Array<{
    id: string;
    representation_id: string;
    property_reference: string | null;
    transaction_type: string;
    status: string;
    updated_at: string;
  }>;
  documents: Array<{
    id: string;
    transaction_id: string;
    name: string;
    version: number;
    media_type: string;
    size_bytes: number;
    created_at: string;
  }>;
};

const PREVIEW_SESSION: PortalSession = {
  identity: { subject: "preview", email: "jordan@example.com", name: "Jordan" },
  representations: [{
    id: "representation-preview",
    client_name: "Jordan Ellis",
    representation_type: "buyer",
    status: "active",
    effective_at: "2026-08-15T00:00:00Z",
    expires_at: null,
  }],
  transactions: [{
    id: "transaction-preview",
    representation_id: "representation-preview",
    property_reference: "12518 Boheme Drive",
    transaction_type: "purchase",
    status: "under_contract",
    updated_at: "2026-08-30T00:00:00Z",
  }],
  documents: [
    {
      id: "document-1",
      transaction_id: "transaction-preview",
      name: "Buyer Representation Agreement.pdf",
      version: 1,
      media_type: "application/pdf",
      size_bytes: 421_888,
      created_at: "2026-08-29T00:00:00Z",
    },
    {
      id: "document-2",
      transaction_id: "transaction-preview",
      name: "Inspection Report.pdf",
      version: 1,
      media_type: "application/pdf",
      size_bytes: 1_258_291,
      created_at: "2026-08-30T00:00:00Z",
    },
  ],
};

export default function App() {
  const keycloakRef = useRef<Keycloak | null>(null);
  const [session, setSession] = useState<PortalSession | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "blocked" | "error">("loading");
  const [message, setMessage] = useState("Connecting to the LeCrown client portal...");

  useEffect(() => {
    let active = true;
    let refreshTimer: number | undefined;

    async function initialize() {
      try {
        if (import.meta.env.DEV && new URLSearchParams(window.location.search).has("preview")) {
          setSession(PREVIEW_SESSION);
          setState("ready");
          return;
        }
        const configResponse = await fetch("/api/client-portal/config", { cache: "no-store" });
        if (!configResponse.ok) throw new Error("The portal configuration could not be loaded.");
        const config = (await configResponse.json()) as PortalConfig;
        if (!config.ready || !config.client_id) {
          setState("blocked");
          setMessage("Client portal sign-in is not configured yet.");
          return;
        }

        const keycloak = new Keycloak({
          url: config.keycloak_url,
          realm: config.realm,
          clientId: config.client_id,
        });
        keycloakRef.current = keycloak;
        const authenticated = await keycloak.init({
          onLoad: "login-required",
          pkceMethod: "S256",
          checkLoginIframe: false,
        });
        if (!authenticated || !keycloak.token) throw new Error("Keycloak sign-in was not completed.");

        const sessionResponse = await fetch("/api/client-portal/session", {
          cache: "no-store",
          headers: { Authorization: `Bearer ${keycloak.token}` },
        });
        if (!sessionResponse.ok) {
          const payload = (await sessionResponse.json().catch(() => null)) as { detail?: string } | null;
          if (sessionResponse.status === 403) {
            setState("blocked");
            setMessage(payload?.detail || "No active client engagement is assigned to this account.");
            return;
          }
          throw new Error(payload?.detail || "The protected client record could not be loaded.");
        }
        const nextSession = (await sessionResponse.json()) as PortalSession;
        if (!active) return;
        setSession(nextSession);
        setState("ready");
        refreshTimer = window.setInterval(() => {
          void keycloak.updateToken(60).catch(() => keycloak.login());
        }, 30_000);
      } catch (error) {
        if (!active) return;
        setState("error");
        setMessage(error instanceof Error ? error.message : "The client portal could not be opened.");
      }
    }

    void initialize();
    return () => {
      active = false;
      if (refreshTimer) window.clearInterval(refreshTimer);
    };
  }, []);

  function logout() {
    void keycloakRef.current?.logout({ redirectUri: window.location.origin });
  }

  if (state !== "ready" || !session) {
    return (
      <main className="portal-shell centered-shell">
        <section className="brand-card">
          <p className="gate-brand">LeCrown Properties</p>
          <h1>{state === "blocked" ? "Access not assigned" : state === "error" ? "Portal unavailable" : "Private client portal"}</h1>
          <p>{message}</p>
          {keycloakRef.current ? <button onClick={logout}><SignOutIcon />Sign out</button> : null}
        </section>
      </main>
    );
  }

  return (
    <main className="portal-shell">
      <header className="brand-bar">
        <a className="brand-name" href="/" aria-label="LeCrown Properties client portal">LeCrown Properties</a>
        <button className="secondary-button" onClick={logout}><SignOutIcon />Sign out</button>
      </header>

      <section className="welcome-block">
        <h1>Welcome, {session.identity.name}</h1>
        <p>Secure records assigned to {session.identity.email}</p>
      </section>

      <section className="summary-rail" aria-label="Portal summary">
        <div><strong>{session.representations.length}</strong><span>{pluralize(session.representations.length, "engagement")}</span></div>
        <div><strong>{session.transactions.length}</strong><span>{pluralize(session.transactions.length, "transaction")}</span></div>
        <div><strong>{session.documents.length}</strong><span>shared documents</span></div>
      </section>

      <section className="content-grid">
        <article className="panel">
          <h2>Your representation</h2>
          {session.representations.length ? session.representations.map((item) => (
            <div className="detail-list" key={item.id}>
              <div><span>Type</span><strong>{titleCase(item.representation_type)} representation</strong></div>
              <div><span>Representative</span><strong>{item.client_name}</strong></div>
              <div><span>Status</span><strong className="status-label success">{titleCase(item.status)}</strong></div>
            </div>
          )) : <p className="empty-state">No active engagement records are available.</p>}
        </article>

        <article className="panel">
          <h2>Transaction status</h2>
          {session.transactions.length ? session.transactions.map((item) => (
            <div className="detail-list" key={item.id}>
              <div><span>Property</span><strong>{item.property_reference || titleCase(item.transaction_type)}</strong></div>
              <div><span>Last updated</span><strong>Updated {formatDate(item.updated_at)}</strong></div>
              <div><span>Status</span><strong className="status-label pending">{titleCase(item.status)}</strong></div>
            </div>
          )) : <p className="empty-state">No transaction milestones have been published.</p>}
        </article>

        <article className="panel documents-panel">
          <h2>Approved client copies</h2>
          {session.documents.length ? (
            <div className="document-table" role="table" aria-label="Approved client documents">
              <div className="document-row document-header" role="row">
                <span role="columnheader">Document name</span><span role="columnheader">Version</span>
                <span role="columnheader">Date</span><span role="columnheader">File size</span><span role="columnheader">Status</span>
              </div>
              {session.documents.map((item) => (
                <div className="document-row" role="row" key={item.id}>
                  <strong role="cell">{item.name}</strong><span role="cell">v{item.version}.0</span>
                  <span role="cell">{formatDate(item.created_at)}</span><span role="cell">{formatBytes(item.size_bytes)}</span>
                  <span role="cell"><strong className="status-label success">Ready</strong></span>
                </div>
              ))}
            </div>
          ) : <p className="empty-state">No documents have been released to your portal yet.</p>}
        </article>
      </section>
    </main>
  );
}

function titleCase(value: string): string {
  return value.replace(/[_-]/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function pluralize(value: number, singular: string): string {
  return value === 1 ? singular : `${singular}s`;
}

function SignOutIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18">
      <path d="M10 5H5v14h5M14 8l4 4-4 4M8 12h10" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
