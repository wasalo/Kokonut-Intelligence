import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { GatewayRequestError, LatestRequest, requestOperatorJson } from "@kokonut/operator-client";
import { useOperatorSession } from "@kokonut/operator-client/react";

type PolygonGeoJSON = {
  type: "Polygon";
  coordinates: number[][][];
};

interface OrganizationOption {
  id: string;
  org_key: string;
  name: string;
}

interface LocationSetupResult {
  location_id: string;
  location_created: boolean;
  location_name: string;
  farm_id: string;
  farm_created: boolean;
  farm_name: string;
  organization_id: string;
  organization_name: string;
  starter_scopes: Array<{ resource: string; action: string; location_id: string }>;
}

const ORGANIZATION_FIELDS = "id,name,org_key";
const RESULT_FIELDS = "farm_created,farm_id,farm_name,location_created,location_id,location_name,organization_id,organization_name,starter_scopes";
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function parseOrganizations(value: unknown): OrganizationOption[] {
  if (!isRecord(value) || Object.keys(value).sort().join(",") !== "data" || !Array.isArray(value.data) || value.data.length > 200) {
    throw new Error("Organization choices did not match the Gateway response contract.");
  }
  return value.data.map((item) => {
    if (
      !isRecord(item) || Object.keys(item).sort().join(",") !== ORGANIZATION_FIELDS ||
      typeof item.id !== "string" || !UUID_PATTERN.test(item.id) ||
      typeof item.org_key !== "string" || typeof item.name !== "string"
    ) {
      throw new Error("Organization choices did not match the Gateway response contract.");
    }
    return { id: item.id, org_key: item.org_key, name: item.name };
  });
}

function parseSetupResult(value: unknown): LocationSetupResult {
  if (!isRecord(value) || Object.keys(value).sort().join(",") !== "data" || !isRecord(value.data)) {
    throw new Error("The setup result did not match the Gateway response contract.");
  }
  const data = value.data;
  if (
    Object.keys(data).sort().join(",") !== RESULT_FIELDS ||
    typeof data.location_id !== "string" || !UUID_PATTERN.test(data.location_id) ||
    typeof data.location_created !== "boolean" ||
    typeof data.farm_id !== "string" || !UUID_PATTERN.test(data.farm_id) ||
    typeof data.farm_created !== "boolean" ||
    typeof data.organization_id !== "string" || !UUID_PATTERN.test(data.organization_id) ||
    typeof data.location_name !== "string" || typeof data.farm_name !== "string" ||
    typeof data.organization_name !== "string" || !Array.isArray(data.starter_scopes) ||
    data.starter_scopes.length < 1 || data.starter_scopes.length > 10
  ) {
    throw new Error("The setup result did not match the Gateway response contract.");
  }
  const starterScopes = data.starter_scopes.map((scope) => {
    if (
      !isRecord(scope) ||
      Object.keys(scope).sort().join(",") !== "action,location_id,resource" ||
      typeof scope.resource !== "string" || typeof scope.action !== "string" ||
      typeof scope.location_id !== "string" || scope.location_id !== data.location_id
    ) {
      throw new Error("The setup result contained an invalid starter scope.");
    }
    return { resource: scope.resource, action: scope.action, location_id: scope.location_id };
  });
  return {
    location_id: data.location_id,
    location_created: data.location_created,
    location_name: data.location_name,
    farm_id: data.farm_id,
    farm_created: data.farm_created,
    farm_name: data.farm_name,
    organization_id: data.organization_id,
    organization_name: data.organization_name,
    starter_scopes: starterScopes,
  };
}

function slugify(value: string): string {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 255);
}

function parsePolygonGeoJSON(text: string): PolygonGeoJSON {
  if (new TextEncoder().encode(text).length > 262_144) {
    throw new Error("Boundary GeoJSON must be 256 KB or smaller.");
  }
  const parsed: unknown = JSON.parse(text);
  const geometry = isRecord(parsed) && parsed.type === "Feature" ? parsed.geometry : parsed;
  if (
    !isRecord(geometry) || geometry.type !== "Polygon" ||
    Object.keys(geometry).sort().join(",") !== "coordinates,type" ||
    !Array.isArray(geometry.coordinates) || geometry.coordinates.length === 0
  ) {
    throw new Error("Choose a GeoJSON Polygon in WGS84 coordinates.");
  }
  for (const ring of geometry.coordinates) {
    if (!Array.isArray(ring) || ring.length < 4) {
      throw new Error("Each boundary ring must contain at least four coordinates.");
    }
    const points: number[][] = [];
    for (const point of ring) {
      if (
        !Array.isArray(point) || point.length !== 2 ||
        point.some((coordinate) => typeof coordinate !== "number" || !Number.isFinite(coordinate))
      ) {
        throw new Error("Boundary coordinates must be numeric longitude/latitude pairs.");
      }
      const [longitude, latitude] = point as number[];
      if (longitude < -180 || longitude > 180 || latitude < -90 || latitude > 90) {
        throw new Error("Boundary coordinates must use valid WGS84 longitude/latitude ranges.");
      }
      points.push([longitude, latitude]);
    }
    const lastPoint = points[points.length - 1];
    if (points[0][0] !== lastPoint[0] || points[0][1] !== lastPoint[1]) {
      throw new Error("Each boundary ring must be closed by repeating its first coordinate.");
    }
  }
  return geometry as PolygonGeoJSON;
}

function boundaryPointCount(boundary: PolygonGeoJSON): number {
  return boundary.coordinates.reduce((count, ring) => count + ring.length, 0);
}

function boundaryPreviewPath(boundary: PolygonGeoJSON): string {
  const points = boundary.coordinates.reduce<number[][]>((all, ring) => all.concat(ring), []);
  const longitudes = points.map(([longitude]) => longitude);
  const latitudes = points.map(([, latitude]) => latitude);
  const minLongitude = Math.min(...longitudes);
  const maxLongitude = Math.max(...longitudes);
  const minLatitude = Math.min(...latitudes);
  const maxLatitude = Math.max(...latitudes);
  const width = maxLongitude - minLongitude || 0.000001;
  const height = maxLatitude - minLatitude || 0.000001;
  const scale = Math.min(288 / width, 148 / height);
  const offsetX = (320 - width * scale) / 2;
  const offsetY = (180 - height * scale) / 2;
  return boundary.coordinates.map((ring) => ring.map(([longitude, latitude], index) => {
    const x = offsetX + (longitude - minLongitude) * scale;
    const y = 180 - offsetY - (latitude - minLatitude) * scale;
    return `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
  }).join(" ") + " Z").join(" ");
}

function boundaryError(error: unknown): string {
  if (error instanceof GatewayRequestError) {
    if (error.status === 401) return "Your operator session expired. Sign in again to continue.";
    if (error.status === 403) return "This account is not authorized for location setup. Ask a platform administrator to grant the location setup capability.";
    if (error.status === 409) return error.message;
    if (error.status === 503) return "Location setup is temporarily unavailable. Try again shortly.";
  }
  return error instanceof Error ? error.message : "Location setup could not be completed.";
}

function BoundaryUploadField({
  id,
  label,
  helpText,
  boundary,
  onChange,
}: {
  id: string;
  label: string;
  helpText: string;
  boundary: PolygonGeoJSON | null;
  onChange: (boundary: PolygonGeoJSON | null, message: string) => void;
}) {
  const [pastedGeoJSON, setPastedGeoJSON] = useState("");
  const [pasteError, setPasteError] = useState("");

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 262_144) {
      const message = "Boundary GeoJSON must be 256 KB or smaller.";
      setPasteError(message);
      onChange(null, message);
      event.target.value = "";
      return;
    }
    try {
      const geometry = parsePolygonGeoJSON(await file.text());
      setPastedGeoJSON(JSON.stringify(geometry, null, 2));
      setPasteError("");
      onChange(geometry, "");
    } catch (error) {
      const message = error instanceof Error ? error.message : "The boundary file could not be read.";
      setPasteError(message);
      onChange(null, message);
    }
    event.target.value = "";
  }

  function loadPastedBoundary() {
    try {
      const geometry = parsePolygonGeoJSON(pastedGeoJSON);
      setPasteError("");
      onChange(geometry, "");
    } catch (error) {
      const message = error instanceof Error ? error.message : "The pasted boundary could not be read.";
      setPasteError(message);
      onChange(null, message);
    }
  }

  return (
    <div className="location-setup__field location-setup__field-wide">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="file"
        accept=".geojson,.json,application/geo+json,application/json"
        onChange={(event) => void handleFile(event)}
        aria-describedby={pasteError ? `${id}-hint ${id}-status ${id}-error` : `${id}-hint ${id}-status`}
      />
      <p className="location-setup__help" id={`${id}-hint`}>
        {helpText} Upload a GeoJSON Polygon exported in WGS84, or paste its geometry below. Coordinates use longitude, latitude order.
      </p>
      <label className="location-setup__help" htmlFor={`${id}-geojson`}>Paste GeoJSON Polygon</label>
      <textarea
        id={`${id}-geojson`}
        rows={5}
        maxLength={262_144}
        spellCheck={false}
        value={pastedGeoJSON}
        onChange={(event) => {
          setPastedGeoJSON(event.target.value);
          setPasteError("");
          onChange(null, "");
        }}
      />
      <button className="location-setup__secondary-action" type="button" onClick={loadPastedBoundary}>
        Use pasted boundary
      </button>
      {pasteError ? <p className="location-setup__alert" id={`${id}-error`} role="alert">{pasteError}</p> : null}
      <p className="location-setup__boundary-status" id={`${id}-status`} role="status">
        {boundary
          ? `Polygon loaded: ${boundary.coordinates.length} ring(s), ${boundaryPointCount(boundary)} points.`
          : "No boundary loaded yet."}
      </p>
      {boundary ? (
        <figure className="location-setup__boundary-preview">
          <svg viewBox="0 0 320 180" role="img" aria-label={`${label} boundary outline preview`}>
            <path d={boundaryPreviewPath(boundary)} />
          </svg>
          <figcaption>Outline preview only; confirm coordinates and source before saving.</figcaption>
        </figure>
      ) : null}
    </div>
  );
}

export function LocationSetupPage() {
  const sessionState = useOperatorSession();
  const session = sessionState.status === "ready" ? sessionState.session : null;
  const organizationRequest = useRef(new LatestRequest());
  const [organizations, setOrganizations] = useState<OrganizationOption[]>([]);
  const [organizationError, setOrganizationError] = useState("");
  const [selectedOrganizationId, setSelectedOrganizationId] = useState("");
  const [locationName, setLocationName] = useState("");
  const [locationSlug, setLocationSlug] = useState("");
  const [locationSlugEdited, setLocationSlugEdited] = useState(false);
  const [country, setCountry] = useState("");
  const [region, setRegion] = useState("");
  const [subRegion, setSubRegion] = useState("");
  const [timezone, setTimezone] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [locationDescription, setLocationDescription] = useState("");
  const [locationBoundary, setLocationBoundary] = useState<PolygonGeoJSON | null>(null);
  const [locationBoundaryError, setLocationBoundaryError] = useState("");
  const [farmName, setFarmName] = useState("");
  const [farmSlug, setFarmSlug] = useState("");
  const [farmSlugEdited, setFarmSlugEdited] = useState(false);
  const [farmType, setFarmType] = useState("syntropic");
  const [farmArea, setFarmArea] = useState("");
  const [farmAreaUnit, setFarmAreaUnit] = useState("hectares");
  const [farmDescription, setFarmDescription] = useState("");
  const [farmBoundary, setFarmBoundary] = useState<PolygonGeoJSON | null>(null);
  const [farmBoundaryError, setFarmBoundaryError] = useState("");
  const [sameBoundary, setSameBoundary] = useState(false);
  const [ownerDecisionReference, setOwnerDecisionReference] = useState("");
  const [ownerDecisionConfirmed, setOwnerDecisionConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [result, setResult] = useState<LocationSetupResult | null>(null);

  useEffect(() => {
    if (!session) {
      setOrganizations([]);
      setOrganizationError("");
      return;
    }
    setOrganizations([]);
    setOrganizationError("");
    const current = organizationRequest.current.begin();
    void requestOperatorJson<unknown>("/operator/api/location-setup/organizations", {
      signal: current.signal,
    })
      .then((payload) => {
        if (!current.isCurrent()) return;
        const options = parseOrganizations(payload);
        setOrganizations(options);
        setSelectedOrganizationId((selected) =>
          options.some((organization) => organization.id === selected)
            ? selected
            : options[0]?.id ?? "",
        );
      })
      .catch((error: unknown) => {
        if (!current.isCurrent() || (error instanceof Error && error.name === "AbortError")) return;
        setOrganizationError(boundaryError(error));
      });
    return () => organizationRequest.current.cancel();
  }, [session?.operator.operator_id]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setSubmitError("");
    setResult(null);
    try {
      if (!locationBoundary) throw new Error("Upload the location boundary before saving.");
      if (!sameBoundary && !farmBoundary) throw new Error("Upload the farm boundary or confirm it matches the location boundary.");
      const selectedOrganization = organizations.find((organization) => organization.id === selectedOrganizationId);
      if (!selectedOrganization) throw new Error("Choose an active tenant organization.");
      const latitudeValue = Number(latitude);
      const longitudeValue = Number(longitude);
      const farmAreaValue = Number(farmArea);
      if (!Number.isFinite(latitudeValue) || !Number.isFinite(longitudeValue)) {
        throw new Error("Enter valid latitude and longitude values.");
      }
      if (!Number.isFinite(farmAreaValue) || farmAreaValue <= 0) {
        throw new Error("Enter a farm area greater than zero.");
      }
      if (!ownerDecisionConfirmed) {
        throw new Error("Confirm the tenant assignment before saving.");
      }
      const payload = {
        organization_id: selectedOrganization.id,
        owner_decision_reference: ownerDecisionReference.trim(),
        owner_decision_confirmed: true,
        location: {
          name: locationName.trim(),
          slug: locationSlug.trim(),
          description: locationDescription.trim() || null,
          country: country.trim(),
          region: region.trim(),
          sub_region: subRegion.trim() || null,
          timezone: timezone.trim(),
          latitude: latitudeValue,
          longitude: longitudeValue,
          boundary_geojson: locationBoundary,
        },
        farm: {
          name: farmName.trim(),
          slug: farmSlug.trim(),
          description: farmDescription.trim() || null,
          farm_type: farmType,
          total_area: farmAreaValue,
          area_unit: farmAreaUnit,
          boundary_geojson: sameBoundary ? locationBoundary : farmBoundary,
        },
      };
      const response = await requestOperatorJson<unknown>("/operator/api/location-setup", {
        method: "POST",
        body: payload,
      });
      setResult(parseSetupResult(response));
    } catch (error) {
      setSubmitError(boundaryError(error));
    } finally {
      setSubmitting(false);
    }
  }

  if (sessionState.status === "loading") {
    return <section aria-busy="true"><p className="eyebrow">Administration</p><h2>Set up a location</h2><p role="status">Checking your operator session…</p></section>;
  }
  if (sessionState.status === "signed-out") {
    return (
      <section aria-labelledby="location-setup-heading">
        <p className="eyebrow">Administration</p>
        <h2 id="location-setup-heading">Set up a location</h2>
        <p className="lead">Sign in with your operator account to register a farm location.</p>
        <a className="button-link" href="/operator/auth/login?return_to=%2Fops%2Fadministration">Sign in to continue</a>
      </section>
    );
  }
  if (sessionState.status === "error") {
    return <section><p className="eyebrow">Administration</p><h2>Set up a location</h2><p role="alert">{sessionState.message}</p></section>;
  }

  if (result) {
    const setupSummary = result.location_created && result.farm_created
      ? `The location and ${result.farm_name} farm were created`
      : `The setup was saved for ${result.location_name} and ${result.farm_name}`;
    return (
      <section aria-labelledby="location-setup-success-heading">
        <p className="eyebrow">Administration · Complete</p>
        <h2 id="location-setup-success-heading">{result.location_name} is ready for data entry</h2>
        <p className="lead">
          {setupSummary} under {result.organization_name}. Any existing baseline and historical records were preserved. No provider request or reference-data import was run.
        </p>
        <dl className="location-setup__result">
          <div><dt>Location ID</dt><dd>{result.location_id}</dd></div>
          <div><dt>Farm ID</dt><dd>{result.farm_id}</dd></div>
          <div><dt>Starter access</dt><dd>Location read and draft-only farm activity entry. Verification and publication remain separate.</dd></div>
        </dl>
        <div className="workflow-grid">
          <article className="workflow-card">
            <div><p className="eyebrow">Continue setup</p><h3>Open the current operator console</h3><p>Use its supported location-scoped farm-activity and review forms. Other farm setup screens are still being migrated.</p></div>
            <a className="button-link" href="/operator/">Open operator console</a>
          </article>
          <article className="workflow-card workflow-card-muted">
            <div><p className="eyebrow">Field operations</p><h3>Check the field workspace</h3><p>Review the location from the Field Operations workspace.</p></div>
            <a className="button-link" href="/field/records">Open field records</a>
          </article>
        </div>
      </section>
    );
  }

  return (
    <section aria-labelledby="location-setup-heading">
      <p className="eyebrow">Administration · Farm onboarding</p>
      <h2 id="location-setup-heading">Set up a location and farm</h2>
      <p className="lead">
        Enter the farm’s operating location and boundary first. The current operator console still handles the supported field-activity forms while the remaining data-entry screens are migrated.
      </p>
      <p className="migration-note" role="note">
        Saving creates or completes the location and farm together. Existing baseline and historical records are preserved; a record assigned to another tenant cannot be changed here. The creator receives location read and draft-only farm activity access, without review or publication permissions.
      </p>

      {organizationError ? <p className="location-setup__alert" role="alert">{organizationError}</p> : null}
      {!organizationError && organizations.length === 0 ? (
        <p className="location-setup__alert" role="status">No active tenant organizations are available for this account.</p>
      ) : null}

      {organizations.length > 0 ? (
        <form className="location-setup__form" onSubmit={(event) => void handleSubmit(event)}>
          <fieldset disabled={submitting}>
            <legend>Tenant assignment</legend>
            <div className="location-setup__grid">
              <div className="location-setup__field location-setup__field-wide">
                <label htmlFor="location-setup-organization">Tenant organization</label>
                <select id="location-setup-organization" value={selectedOrganizationId} onChange={(event) => setSelectedOrganizationId(event.target.value)} required>
                  {organizations.map((organization) => (
                    <option key={organization.id} value={organization.id}>{organization.name} · {organization.org_key}</option>
                  ))}
                </select>
                <p className="location-setup__help">This chooses the Kokonut tenant that administers the record. It does not establish land title.</p>
              </div>
              <div className="location-setup__field location-setup__field-wide">
                <label htmlFor="location-setup-owner-reference">Owner/tenant decision reference</label>
                <input id="location-setup-owner-reference" value={ownerDecisionReference} onChange={(event) => setOwnerDecisionReference(event.target.value)} minLength={3} maxLength={2000} required />
                <p className="location-setup__help">Use an owner approval, agreement, or internal decision reference. Do not enter private personal details.</p>
              </div>
              <label className="location-setup__check location-setup__field-wide">
                <input type="checkbox" checked={ownerDecisionConfirmed} onChange={(event) => setOwnerDecisionConfirmed(event.target.checked)} required />
                <span>I am authorized to assign this location to the selected tenant organization.</span>
              </label>
            </div>
          </fieldset>

          <fieldset disabled={submitting}>
            <legend>Location details</legend>
            <div className="location-setup__grid">
              <div className="location-setup__field"><label htmlFor="location-name">Location name</label><input id="location-name" value={locationName} onChange={(event) => { const value = event.target.value; setLocationName(value); if (!locationSlugEdited) setLocationSlug(slugify(value)); }} required maxLength={255} /></div>
              <div className="location-setup__field"><label htmlFor="location-slug">Location slug</label><input id="location-slug" value={locationSlug} onChange={(event) => { setLocationSlug(event.target.value); setLocationSlugEdited(true); }} pattern="[a-z0-9]+(-[a-z0-9]+)*" required maxLength={255} /><span className="location-setup__help">Lowercase letters, numbers, and hyphens.</span></div>
              <div className="location-setup__field"><label htmlFor="location-country">Country</label><input id="location-country" value={country} onChange={(event) => setCountry(event.target.value)} required maxLength={100} /></div>
              <div className="location-setup__field"><label htmlFor="location-region">Region or province</label><input id="location-region" value={region} onChange={(event) => setRegion(event.target.value)} required maxLength={255} /></div>
              <div className="location-setup__field"><label htmlFor="location-sub-region">Municipality or sub-region</label><input id="location-sub-region" value={subRegion} onChange={(event) => setSubRegion(event.target.value)} maxLength={255} /></div>
              <div className="location-setup__field"><label htmlFor="location-timezone">IANA time zone</label><input id="location-timezone" value={timezone} onChange={(event) => setTimezone(event.target.value)} placeholder="America/Santo_Domingo" required maxLength={50} /></div>
              <div className="location-setup__field"><label htmlFor="location-latitude">Latitude</label><input id="location-latitude" type="number" min="-90" max="90" step="any" value={latitude} onChange={(event) => setLatitude(event.target.value)} required /></div>
              <div className="location-setup__field"><label htmlFor="location-longitude">Longitude</label><input id="location-longitude" type="number" min="-180" max="180" step="any" value={longitude} onChange={(event) => setLongitude(event.target.value)} required /></div>
              <div className="location-setup__field location-setup__field-wide"><label htmlFor="location-description">Description</label><textarea id="location-description" value={locationDescription} onChange={(event) => setLocationDescription(event.target.value)} rows={3} maxLength={2000} /></div>
              <BoundaryUploadField id="location-boundary" label="Location boundary" helpText="This defines the farm’s spatial extent; the representative coordinates must fall inside it." boundary={locationBoundary} onChange={(value, message) => { setLocationBoundary(value); setLocationBoundaryError(message); if (sameBoundary) setFarmBoundary(value); }} />
              {locationBoundaryError ? <p className="location-setup__field-wide location-setup__alert" role="alert">{locationBoundaryError}</p> : null}
            </div>
          </fieldset>

          <fieldset disabled={submitting}>
            <legend>Farm details</legend>
            <div className="location-setup__grid">
              <div className="location-setup__field"><label htmlFor="farm-name">Farm name</label><input id="farm-name" value={farmName} onChange={(event) => { const value = event.target.value; setFarmName(value); if (!farmSlugEdited) setFarmSlug(slugify(value)); }} required maxLength={255} /></div>
              <div className="location-setup__field"><label htmlFor="farm-slug">Farm slug</label><input id="farm-slug" value={farmSlug} onChange={(event) => { setFarmSlug(event.target.value); setFarmSlugEdited(true); }} pattern="[a-z0-9]+(-[a-z0-9]+)*" required maxLength={255} /><span className="location-setup__help">Lowercase letters, numbers, and hyphens.</span></div>
              <div className="location-setup__field"><label htmlFor="farm-type">Farm type</label><select id="farm-type" value={farmType} onChange={(event) => setFarmType(event.target.value)}><option value="syntropic">Syntropic</option><option value="agroforestry">Agroforestry</option><option value="organic">Organic</option><option value="hybrid">Hybrid</option><option value="conventional">Conventional</option></select></div>
              <div className="location-setup__field"><label htmlFor="farm-area">Farm area</label><input id="farm-area" type="number" min="0.0001" step="0.0001" value={farmArea} onChange={(event) => setFarmArea(event.target.value)} required /></div>
              <div className="location-setup__field"><label htmlFor="farm-area-unit">Area unit</label><select id="farm-area-unit" value={farmAreaUnit} onChange={(event) => setFarmAreaUnit(event.target.value)}><option value="hectares">Hectares</option><option value="acres">Acres</option><option value="square_meters">Square meters</option></select></div>
              <div className="location-setup__field location-setup__field-wide"><label htmlFor="farm-description">Description</label><textarea id="farm-description" value={farmDescription} onChange={(event) => setFarmDescription(event.target.value)} rows={3} maxLength={2000} /></div>
              <div className="location-setup__field location-setup__field-wide">
                <label className="location-setup__check">
                  <input type="checkbox" checked={sameBoundary} onChange={(event) => { const checked = event.target.checked; setSameBoundary(checked); setFarmBoundary(checked ? locationBoundary : null); setFarmBoundaryError(""); }} disabled={!locationBoundary} />
                  <span>The farm boundary is the same as the location boundary.</span>
                </label>
              </div>
              {!sameBoundary ? <BoundaryUploadField id="farm-boundary" label="Farm boundary" helpText="This polygon must fit inside the location boundary." boundary={farmBoundary} onChange={(value, message) => { setFarmBoundary(value); setFarmBoundaryError(message); }} /> : null}
              {farmBoundaryError ? <p className="location-setup__field-wide location-setup__alert" role="alert">{farmBoundaryError}</p> : null}
            </div>
          </fieldset>

          {submitError ? <p className="location-setup__alert" role="alert">{submitError}</p> : null}
          <div className="location-setup__actions">
            <button className="button-link" type="submit" disabled={submitting || !ownerDecisionConfirmed || !locationBoundary || (!sameBoundary && !farmBoundary)}>
              {submitting ? "Saving setup…" : "Save location and farm setup"}
            </button>
            {submitting ? <span role="status">Saving both records and the tenant decision in one transaction…</span> : null}
          </div>
        </form>
      ) : null}
    </section>
  );
}
