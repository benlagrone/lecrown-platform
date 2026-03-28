import { useEffect, useState, type FormEvent } from "react";

import {
  createContent,
  listContent,
  listInquiries,
  publishDistribution,
  publishToLinkedIn,
} from "../../shared/api";
import type { Content, ContentCreate, DistributionChannel, Inquiry, Tenant } from "../../shared/types";

function buildInitialForm(tenant: Tenant = "development"): ContentCreate {
  return {
    tenant,
    type: "insight",
    title: "",
    body: "",
    tags: [],
    distribution: {
      linkedin: false,
      youtube: false,
      website: true,
      twitter: false,
    },
    media: {
      video_generated: false,
      video_path: "",
      youtube_video_id: null,
      youtube_status: null,
    },
    publish_linkedin: false,
    publish_site: true,
  };
}

export default function App() {
  const [tenant, setTenant] = useState<Tenant>("development");
  const [form, setForm] = useState<ContentCreate>(buildInitialForm());
  const [contentItems, setContentItems] = useState<Content[]>([]);
  const [inquiries, setInquiries] = useState<Inquiry[]>([]);
  const [message, setMessage] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    void refreshContent(tenant);
    if (tenant === "properties") {
      void refreshInquiries();
    }
  }, [tenant]);

  async function refreshContent(selectedTenant: Tenant) {
    try {
      const items = await listContent(selectedTenant);
      setContentItems(items);
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  async function refreshInquiries() {
    try {
      const items = await listInquiries();
      setInquiries(items);
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setMessage("");

    try {
      const payload: ContentCreate = {
        ...form,
        tenant,
        publish_linkedin: form.distribution.linkedin,
        publish_site: form.distribution.website,
      };
      await createContent(payload);
      setForm(buildInitialForm(tenant));
      setMessage("Content saved.");
      await refreshContent(tenant);
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  async function handlePublish(contentId: string) {
    setMessage("");
    try {
      await publishToLinkedIn(contentId);
      setMessage("LinkedIn publish request completed.");
      await refreshContent(tenant);
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  async function handleDistribution(item: Content) {
    const channels = getEnabledChannels(item);
    if (channels.length === 0) {
      setMessage("Enable at least one distribution channel first.");
      return;
    }

    setMessage("");
    try {
      const result = await publishDistribution(item.id, channels, item.media.video_path ?? undefined);
      const statuses = Object.entries(result.results)
        .map(([channel, value]) => `${channel}: ${value.status ?? "completed"}`)
        .join(" | ");
      setMessage(`Distribution finished. ${statuses}`);
      await refreshContent(tenant);
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  return (
    <main className="page-shell">
      <section className="hero-card">
        <div>
          <p className="eyebrow">LeCrown Platform</p>
          <h1>Multi-tenant content and inquiry control room</h1>
          <p className="hero-copy">
            One backend, two business surfaces. Switch tenants, create content, and push live when the
            publishing path is ready.
          </p>
        </div>

        <label className="tenant-picker">
          <span>Tenant</span>
          <select
            value={tenant}
            onChange={(event) => {
              const nextTenant = event.target.value as Tenant;
              setTenant(nextTenant);
              setForm(buildInitialForm(nextTenant));
            }}
          >
            <option value="development">Development</option>
            <option value="properties">Properties</option>
          </select>
        </label>
      </section>

      {message ? <div className="message-banner">{message}</div> : null}

      <section className="grid">
        <article className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Create Content</p>
              <h2>Draft once, route by tenant</h2>
            </div>
          </div>

          <form className="content-form" onSubmit={handleSubmit}>
            <label>
              <span>Type</span>
              <input
                value={form.type}
                onChange={(event) => setForm((current) => ({ ...current, type: event.target.value }))}
                placeholder="insight"
              />
            </label>

            <label>
              <span>Title</span>
              <input
                value={form.title}
                onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                placeholder="What changed in the market this week?"
              />
            </label>

            <label>
              <span>Body</span>
              <textarea
                rows={8}
                value={form.body}
                onChange={(event) => setForm((current) => ({ ...current, body: event.target.value }))}
                placeholder="Write the actual post body here."
              />
            </label>

            <label>
              <span>Tags</span>
              <input
                value={form.tags.join(", ")}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    tags: event.target.value
                      .split(",")
                      .map((tag) => tag.trim())
                      .filter(Boolean),
                  }))
                }
                placeholder="houston, multifamily, acquisition"
              />
            </label>

            <div className="toggle-row">
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={form.distribution.linkedin}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      distribution: { ...current.distribution, linkedin: event.target.checked },
                      publish_linkedin: event.target.checked,
                    }))
                  }
                />
                <span>Publish to LinkedIn</span>
              </label>

              <label className="toggle">
                <input
                  type="checkbox"
                  checked={form.distribution.youtube}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      distribution: { ...current.distribution, youtube: event.target.checked },
                    }))
                  }
                />
                <span>Publish to YouTube</span>
              </label>

              <label className="toggle">
                <input
                  type="checkbox"
                  checked={form.distribution.website}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      distribution: { ...current.distribution, website: event.target.checked },
                      publish_site: event.target.checked,
                    }))
                  }
                />
                <span>Publish to site</span>
              </label>
            </div>

            {form.distribution.youtube ? (
              <label>
                <span>Video path</span>
                <input
                  value={form.media.video_path ?? ""}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      media: { ...current.media, video_path: event.target.value },
                    }))
                  }
                  placeholder="/videos/warehouse.mp4"
                />
              </label>
            ) : null}

            <button type="submit" disabled={submitting}>
              {submitting ? "Saving..." : "Create content"}
            </button>
          </form>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Content Queue</p>
              <h2>{tenant === "development" ? "Development feed" : "Properties feed"}</h2>
            </div>
          </div>

          <div className="stack">
            {contentItems.length === 0 ? (
              <p className="empty-state">No content has been created for this tenant yet.</p>
            ) : (
              contentItems.map((item) => (
                <div className="content-card" key={item.id}>
                  <div className="content-meta">
                    <strong>{item.title}</strong>
                    <span>{item.type}</span>
                  </div>
                  <p>{item.body}</p>
                  <div className="tag-row">
                    {getEnabledChannels(item).map((channel) => (
                      <span className="tag" key={channel}>
                        {channel}
                      </span>
                    ))}
                  </div>
                  <div className="tag-row">
                    {item.tags.map((tag) => (
                      <span className="tag" key={tag}>
                        {tag}
                      </span>
                    ))}
                  </div>
                  <div className="content-footer">
                    <div className="status-stack">
                      <span>LinkedIn: {item.linkedin_status ?? "not queued"}</span>
                      <span>YouTube: {item.media.youtube_status ?? "not queued"}</span>
                    </div>
                    <div className="action-row">
                      <button type="button" onClick={() => void handlePublish(item.id)}>
                        LinkedIn now
                      </button>
                      <button type="button" onClick={() => void handleDistribution(item)}>
                        Run distribution
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </article>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Inquiry CRM</p>
            <h2>Properties pipeline</h2>
          </div>
        </div>

        {tenant !== "properties" ? (
          <p className="empty-state">Inquiry capture is scoped to the properties tenant.</p>
        ) : inquiries.length === 0 ? (
          <p className="empty-state">No inquiries captured yet.</p>
        ) : (
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>Contact</th>
                  <th>Asset Type</th>
                  <th>Location</th>
                  <th>Problem</th>
                </tr>
              </thead>
              <tbody>
                {inquiries.map((inquiry) => (
                  <tr key={inquiry.id}>
                    <td>
                      <strong>{inquiry.contact_name}</strong>
                      <span>{inquiry.email}</span>
                      <span>{inquiry.phone}</span>
                    </td>
                    <td>{inquiry.asset_type}</td>
                    <td>{inquiry.location}</td>
                    <td>{inquiry.problem}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}

function getEnabledChannels(item: Pick<Content, "distribution">): DistributionChannel[] {
  const channels: DistributionChannel[] = [];
  if (item.distribution.linkedin) {
    channels.push("linkedin");
  }
  if (item.distribution.youtube) {
    channels.push("youtube");
  }
  if (item.distribution.website) {
    channels.push("website");
  }
  if (item.distribution.twitter) {
    channels.push("twitter");
  }
  return channels;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong.";
}
