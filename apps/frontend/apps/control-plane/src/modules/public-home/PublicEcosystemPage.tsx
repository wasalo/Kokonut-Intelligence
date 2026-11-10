import { useEffect, useState } from "react";
import "./public-home.css";

interface PublicLocation {
  id: string;
  name: string;
  country: string | null;
  region: string | null;
  status: "active";
}

interface PublicLocationSummary {
  summary_type: "public_location_summary";
  location_id: string;
  location: PublicLocation;
  metrics: {
    metric_count: number;
    latest_computed_at: string | null;
  };
  attestations: {
    published_count: number;
  };
}

type DirectoryState =
  | { status: "loading"; locations: PublicLocation[] }
  | { status: "ready"; locations: PublicLocation[] }
  | { status: "error"; locations: PublicLocation[] };

let publicDirectoryRequest: Promise<PublicLocation[]> | null = null;

function getPublicDirectory(refresh = false): Promise<PublicLocation[]> {
  if (refresh || !publicDirectoryRequest) {
    const request = fetch("/api/v1/locations", {
      headers: { Accept: "application/json" },
      credentials: "omit",
      cache: "no-cache",
    }).then(async (response) => {
      if (!response.ok) throw new Error("Public directory request failed");
      const payload: unknown = await response.json();
      if (
        !payload ||
        typeof payload !== "object" ||
        !("data" in payload) ||
        !Array.isArray(payload.data)
      ) {
        throw new Error("Public directory response was invalid");
      }
      return payload.data as PublicLocation[];
    });
    const handledRequest = request.catch((error: unknown) => {
      if (publicDirectoryRequest === handledRequest) publicDirectoryRequest = null;
      throw error;
    });
    publicDirectoryRequest = handledRequest;
  }
  return publicDirectoryRequest;
}

function formatPublicDate(value: string | null): string {
  if (!value) return "No published metric update";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Update date unavailable";
  return `Latest metric update ${new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(parsed)}`;
}

function EcosystemMap() {
  return (
    <div className="public-map" aria-hidden="true">
      <svg viewBox="0 0 620 520" role="presentation" focusable="false">
        <defs>
          <radialGradient id="map-glow">
            <stop offset="0" stopColor="#d9f07c" stopOpacity=".21" />
            <stop offset="1" stopColor="#d9f07c" stopOpacity="0" />
          </radialGradient>
          <pattern id="map-dots" width="19" height="19" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="1" fill="#e8f3cb" fillOpacity=".3" />
          </pattern>
        </defs>
        <circle cx="318" cy="256" r="226" fill="url(#map-glow)" />
        <circle cx="318" cy="256" r="226" fill="url(#map-dots)" opacity=".22" />
        <g fill="none" stroke="#d9f07c" strokeOpacity=".14">
          <path d="M26 294c87-104 108-94 178-159s124-95 216-68 112 71 176 32" />
          <path d="M17 333c88-104 117-84 187-149s124-95 216-68 112 71 176 32" />
          <path d="M4 371c91-103 130-80 204-146s124-95 216-68 112 71 176 32" />
          <path d="M38 431c83-95 135-68 208-132s123-94 211-69 110 66 164 31" />
          <path d="M64 469c81-91 138-64 211-128s123-94 211-69 110 66 164 31" />
          <path d="M59 75c49 22 63 53 112 63s90-29 147-5 68 67 125 78 93-13 151 22" />
          <path d="M43 112c49 22 63 53 112 63s90-29 147-5 68 67 125 78 93-13 151 22" />
        </g>
        <g fill="none" stroke="#d9f07c" strokeOpacity=".48" strokeWidth="1.5">
          <path d="M313 253 139 151M313 253l181-116M313 253 147 383M313 253l180 127" />
        </g>
        <circle cx="313" cy="253" r="79" fill="#102f25" stroke="#d9f07c" strokeOpacity=".54" />
        <circle cx="313" cy="253" r="65" fill="none" stroke="#d9f07c" strokeOpacity=".2" />
        <path d="M314 279v-45m0 22c-17 0-28-10-28-27 17 0 28 10 28 27Zm0-18c0-17 11-28 28-28 0 17-11 28-28 28Z" fill="none" stroke="#d9f07c" strokeLinecap="round" strokeLinejoin="round" strokeWidth="4" />
        <g fill="#d9f07c" stroke="#102f25" strokeWidth="6">
          <circle cx="139" cy="151" r="9" />
          <circle cx="494" cy="137" r="9" />
          <circle cx="147" cy="383" r="9" />
          <circle cx="493" cy="380" r="9" />
        </g>
      </svg>
      <span className="public-map__label public-map__label--field">Local operations</span>
      <span className="public-map__label public-map__label--methods">Shared methods</span>
      <span className="public-map__label public-map__label--review">Human review</span>
      <span className="public-map__label public-map__label--public">Public evidence</span>
      <span className="public-map__center-label">Kokonut<br />Intelligence</span>
      <span className="public-map__caption">A connected ecosystem, with decisions kept in context</span>
    </div>
  );
}

function PublicLocationCard({ location }: { location: PublicLocation }) {
  const [expanded, setExpanded] = useState(false);
  const [summary, setSummary] = useState<PublicLocationSummary | null>(null);
  const [summaryState, setSummaryState] = useState<"idle" | "loading" | "ready" | "error">("idle");

  async function toggleSummary() {
    const nextExpanded = !expanded;
    setExpanded(nextExpanded);
    if (!nextExpanded || summary || summaryState === "loading") return;

    setSummaryState("loading");
    try {
      const response = await fetch(`/api/v1/analytics/${encodeURIComponent(location.id)}/summary`, {
        headers: { Accept: "application/json" },
        credentials: "omit",
        cache: "no-cache",
      });
      if (!response.ok) throw new Error("Public summary request failed");
      const payload = await response.json() as { data?: PublicLocationSummary };
      if (!payload.data || payload.data.summary_type !== "public_location_summary") {
        throw new Error("Public summary response was invalid");
      }
      setSummary(payload.data);
      setSummaryState("ready");
    } catch {
      setSummaryState("error");
    }
  }

  const place = [location.region, location.country].filter(Boolean).join(", ");
  return (
    <article className="public-location-card">
      <div>
        <p className="public-location-card__eyebrow">Public location</p>
        <h3>{location.name}</h3>
        <p>{place || "Location details are intentionally limited in this view."}</p>
      </div>
      <button
        type="button"
        className="public-text-action"
        aria-expanded={expanded}
        onClick={() => void toggleSummary()}
      >
        {expanded ? "Hide public summary" : "Explore public summary"}
        <span aria-hidden="true">{expanded ? "−" : "+"}</span>
      </button>
      {expanded ? (
        <div className="public-location-card__summary" aria-live="polite">
          {summaryState === "loading" ? <p role="status">Loading approved public summary…</p> : null}
          {summaryState === "error" ? (
            <p role="status">The public summary is unavailable right now. Please try again later.</p>
          ) : null}
          {summary ? (
            <dl>
              <div>
                <dt>Public metric series</dt>
                <dd>{summary.metrics.metric_count}</dd>
              </div>
              <div>
                <dt>Published attestations</dt>
                <dd>{summary.attestations.published_count}</dd>
              </div>
              <div className="public-location-card__date">
                <dt>Data recency</dt>
                <dd>{formatPublicDate(summary.metrics.latest_computed_at)}</dd>
              </div>
            </dl>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function PublicDirectory() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [directory, setDirectory] = useState<DirectoryState>({ status: "loading", locations: [] });

  useEffect(() => {
    let active = true;
    setDirectory((current) => ({ status: "loading", locations: current.locations }));
    void getPublicDirectory(refreshKey > 0).then(
      (locations) => {
        if (active) setDirectory({ status: "ready", locations });
      },
      () => {
        if (active) setDirectory((current) => ({ status: "error", locations: current.locations }));
      },
    );
    return () => { active = false; };
  }, [refreshKey]);

  return (
    <div className="public-directory">
      <div className="public-directory__stat">
        <span className="public-directory__stat-label">Locations in public view</span>
        <strong aria-live="polite">
          {directory.status === "loading" ? "…" : directory.status === "error" ? "—" : directory.locations.length}
        </strong>
        <span className="public-directory__stat-footnote">Only records explicitly cleared for public projection</span>
      </div>
      <div className="public-directory__content">
        {directory.status === "loading" ? <p className="public-status" role="status">Reading the public directory…</p> : null}
        {directory.status === "error" ? (
          <div className="public-empty-state" role="status">
            <div className="public-empty-state__icon" aria-hidden="true">↻</div>
            <div>
              <h3>Public data is temporarily unavailable</h3>
              <p>The public directory could not be reached. Try again in a moment.</p>
              <button type="button" className="public-text-action" onClick={() => setRefreshKey((key) => key + 1)}>
                Retry directory <span aria-hidden="true">↗</span>
              </button>
            </div>
          </div>
        ) : null}
        {directory.status === "ready" && directory.locations.length === 0 ? (
          <div className="public-empty-state">
            <div className="public-empty-state__icon" aria-hidden="true">◎</div>
            <div>
              <h3>The public view is being prepared</h3>
              <p>No locations are currently included in the public directory. A location appears here only through the platform’s governed public projection.</p>
              <a className="public-text-action" href="https://kokonut.network/ecosystem-wiki/kokonut-farms/adelphi/summary">
                Meet the Kokonut Adelphi reference farm <span aria-hidden="true">↗</span>
              </a>
            </div>
          </div>
        ) : null}
        {directory.status === "ready" && directory.locations.length > 0 ? (
          <div className="public-location-list">
            {directory.locations.map((location) => <PublicLocationCard key={location.id} location={location} />)}
          </div>
        ) : null}
        <a className="public-directory__source" href="/api/v1/locations">
          Inspect the public directory response <span aria-hidden="true">↗</span>
        </a>
      </div>
    </div>
  );
}

const WORKSPACES = [
  {
    number: "01",
    name: "General Operations",
    description: "Set up locations, coordinate operational records, and work with reports and governed metrics.",
    href: "/ops/",
    action: "Explore operations",
    className: "operations",
  },
  {
    number: "02",
    name: "Field Operations",
    description: "Capture location-scoped activity and handle field submissions through a dedicated review path.",
    href: "/field/records",
    action: "Explore field work",
    className: "field",
  },
  {
    number: "03",
    name: "Governance",
    description: "Review coordination recommendations while keeping agent assistance separate from human authority.",
    href: "/governance/",
    action: "Explore governance",
    className: "governance",
  },
] as const;

export function PublicEcosystemPage() {
  return (
    <main className="public-home">
      <a className="public-skip-link" href="#public-main">Skip to content</a>
      <header className="public-header">
        <a className="public-brand" href="/" aria-label="Kokonut Intelligence home">
          <span className="public-brand__mark" aria-hidden="true">K</span>
          <span><strong>Kokonut Intelligence</strong><small>by Kokonut Network</small></span>
        </a>
        <nav className="public-nav" aria-label="Main navigation">
          <a href="#how-it-works">How it works</a>
          <a href="#public-data">Public view</a>
          <a href="#workspaces">Workspaces</a>
          <a className="public-nav__action" href="/operator/auth/login?return_to=%2Fops%2F&prompt=select_account">Operator sign in <span aria-hidden="true">↗</span></a>
        </nav>
      </header>

      <div id="public-main">
        <section className="public-hero" aria-labelledby="public-hero-title">
          <div className="public-hero__inner">
            <div className="public-hero__copy">
              <p className="public-eyebrow"><span className="public-eyebrow__dot" /> Kokonut Network · Open coordination infrastructure</p>
              <h1 id="public-hero-title">A clearer view of a regenerative network.</h1>
              <p className="public-hero__lead">Kokonut Intelligence connects farm operations, governed records, reviewable evidence, and decision support—while keeping local authority and human review in context.</p>
              <div className="public-hero__actions">
                <a className="public-button public-button--light" href="#public-data">Explore the public view <span aria-hidden="true">↓</span></a>
                <a className="public-button public-button--outline" href="/ops/">Open the control plane <span aria-hidden="true">↗</span></a>
              </div>
              <p className="public-hero__note">Open-source platform <span>·</span> Permission-aware <span>·</span> Human-reviewed workflows</p>
            </div>
            <EcosystemMap />
          </div>
          <div className="public-hero__bottomline"><span>GROW</span><span>MEASURE</span><span>VERIFY</span><span>GOVERN</span><span>LEARN</span><span>REGENERATE</span></div>
        </section>

        <section className="public-section public-data-section" id="public-data" aria-labelledby="public-data-title">
          <div className="public-section__intro">
            <div>
              <p className="public-eyebrow public-eyebrow--green">A public window, on purpose</p>
              <h2 id="public-data-title">See what the network has cleared to share.</h2>
            </div>
            <p>Explore an intentionally bounded view of Kokonut’s public records. Internal drafts, operator details, private notes, and exact farm boundaries stay out of this page.</p>
          </div>
          <PublicDirectory />
          <div className="public-data-footnote">
            <span className="public-data-footnote__icon" aria-hidden="true">◉</span>
            <p><strong>Public by decision, not by default.</strong> The figures above come from the live Gateway directory. A workflow status records a review decision; it is not, on its own, scientific certification of an outcome.</p>
          </div>
        </section>

        <section className="public-process-section" id="how-it-works" aria-labelledby="public-process-title">
          <div className="public-section public-process-section__inner">
            <div className="public-section__intro">
              <div>
                <p className="public-eyebrow public-eyebrow--green">From work to shared learning</p>
                <h2 id="public-process-title">A system that keeps evidence in context.</h2>
              </div>
              <p>Different sources, permissions, and reviewers meet in one governed implementation layer. Not every record needs every step.</p>
            </div>
            <ol className="public-flow">
              <li>
                <span className="public-flow__number">01</span>
                <div><h3>Observe</h3><p>Local teams record activity and source information from farm, field, and partner workflows.</p></div>
                <span className="public-flow__tag">Local context</span>
              </li>
              <li>
                <span className="public-flow__number">02</span>
                <div><h3>Structure</h3><p>Records gain clear location, provenance, access boundaries, and a place in the operating model.</p></div>
                <span className="public-flow__tag">Governed data</span>
              </li>
              <li>
                <span className="public-flow__number">03</span>
                <div><h3>Review</h3><p>Human decisions move records through their lifecycle. Analysis and agent drafts remain distinct from approval.</p></div>
                <span className="public-flow__tag">Human judgment</span>
              </li>
              <li>
                <span className="public-flow__number">04</span>
                <div><h3>Share and learn</h3><p>Only eligible public projections are shared; reviewed information can support reporting and future decisions.</p></div>
                <span className="public-flow__tag">Permissioned view</span>
              </li>
            </ol>
            <p className="public-process-note">Measurement is not verification. An attestation is not scientific certification. Intelligence helps make records and their limits easier to inspect.</p>
          </div>
        </section>

        <section className="public-section public-workspaces" id="workspaces" aria-labelledby="public-workspaces-title">
          <div className="public-section__intro">
            <div>
              <p className="public-eyebrow public-eyebrow--green">One control plane, distinct work</p>
              <h2 id="public-workspaces-title">Choose the view that fits your role.</h2>
            </div>
            <p>The Control Plane brings operational, field, and governance workflows into one experience. Permissions and decision rights remain scoped to each job.</p>
          </div>
          <div className="public-workspace-grid">
            {WORKSPACES.map((workspace) => (
              <article className={`public-workspace-card public-workspace-card--${workspace.className}`} key={workspace.number}>
                <span className="public-workspace-card__number">{workspace.number}</span>
                <div>
                  <h3>{workspace.name}</h3>
                  <p>{workspace.description}</p>
                </div>
                <a href={workspace.href}>{workspace.action} <span aria-hidden="true">↗</span></a>
              </article>
            ))}
          </div>
        </section>

        <section className="public-adoption-section" id="adoption" aria-labelledby="public-adoption-title">
          <div className="public-adoption-section__inner">
            <div>
              <p className="public-eyebrow">Grow the future. Regenerate the present.</p>
              <h2 id="public-adoption-title">Build with the network.</h2>
              <p>Kokonut brings together local operators, contributors, researchers, builders, and partners around shared methods, accountable coordination, and evidence-aware technology.</p>
            </div>
            <div className="public-adoption-links">
              <a href="https://kokonut.network/ecosystem-wiki/open-collaboration-invitation">Find a way to contribute <span aria-hidden="true">↗</span></a>
              <a href="https://kokonut.network/build-with-kokonut">Build with Kokonut <span aria-hidden="true">↗</span></a>
              <a href="https://link.kokonut.network/meeting">Talk about adoption <span aria-hidden="true">↗</span></a>
            </div>
          </div>
        </section>
      </div>

      <footer className="public-footer">
        <a className="public-brand public-brand--footer" href="/">
          <span className="public-brand__mark" aria-hidden="true">K</span>
          <span><strong>Kokonut Intelligence</strong><small>Open coordination infrastructure</small></span>
        </a>
        <p>Information is governed. Evidence has context. Decisions stay accountable.</p>
        <nav aria-label="Further reading">
          <a href="https://kokonut.network/llms.txt">Kokonut Network overview</a>
          <a href="https://github.com/wasalo/Kokonut-Public-Site">Knowledge base</a>
          <a href="https://github.com/wasalo/Kokonut-Intelligence">Source code</a>
        </nav>
      </footer>
    </main>
  );
}
