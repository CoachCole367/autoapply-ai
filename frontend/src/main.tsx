import React, { useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

type Job = {
  id: number;
  title: string;
  employer: string;
  location: string;
  description: string;
  url: string;
  expired: boolean;
  match: null | { score: number; explanation: string; decision: string };
};
type Board = { id: number; provider: string; slug: string; employer: string };
type Profile = {
  name: string;
  email: string;
  phone: string;
  location: string;
  skills: string[];
  experience: string[];
  education: string[];
  certifications: string[];
  preferred_titles: string[];
  allowed_locations: string[];
  authorized_countries: string[];
  minimum_salary: number | null;
  answers: Record<string, string>;
  verified: boolean;
};
type Policy = {
  enabled: boolean;
  emergency_stop: boolean;
  dry_run: boolean;
  auto_submit: boolean;
  minimum_score: number;
  review_score: number;
  daily_cap: number;
  interval_hours: number;
  allowed_hosts: string[];
  blocked_employers: string[];
};
type Activity = {
  tasks: { id: number; kind: string; status: string; error: string | null }[];
  events: { id: number; message: string; at: string }[];
};
type Application = {
  id: number;
  job_id: number;
  status: string;
  updated_at: string;
};
type Doc = { id: number; job_id: number };
function App() {
  const [token, setToken] = useState("");
  const [input, setInput] = useState("");
  const [page, setPage] = useState("Overview");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [boards, setBoards] = useState<Board[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [settings, setSettings] = useState<Policy | null>(null);
  const [activity, setActivity] = useState<Activity>({ tasks: [], events: [] });
  const [apps, setApps] = useState<Application[]>([]);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [overview, setOverview] = useState<
    Record<string, string | number | boolean>
  >({});
  const [query, setQuery] = useState("");
  const [board, setBoard] = useState({
    provider: "greenhouse",
    slug: "",
    employer: "",
  });
  const api = useCallback(
    async (path: string, method = "GET", body?: unknown) => {
      const response = await fetch("/api/" + path, {
        method,
        headers: {
          Authorization: "Bearer " + token,
          "Content-Type": "application/json",
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (!response.ok) {
        if (response.status === 401) setToken("");
        const data = await response.json().catch(() => ({}));
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Request failed. Check your input and API connection.",
        );
      }
      return response.json();
    },
    [token],
  );
  const refresh = useCallback(async () => {
    const [j, b, a, o, d, ap] = await Promise.all([
      api("jobs"),
      api("boards"),
      api("activity"),
      api("overview"),
      api("documents"),
      api("applications"),
    ]);
    setJobs(j);
    setBoards(b);
    setActivity(a);
    setOverview(o);
    setDocs(d);
    setApps(ap);
  }, [api]);
  useEffect(() => {
    if (!token) return;
    let live = true;
    Promise.all([api("profile"), api("settings")])
      .then(([p, s]) => {
        if (live) {
          setProfile(p);
          setSettings(s);
        }
      })
      .catch((e) => setError(e.message));
    refresh().catch((e) => setError(e.message));
    const timer = setInterval(
      () => refresh().catch((e) => setError(e.message)),
      5000,
    );
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [token, api, refresh]);
  async function action(fn: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      await refresh();
      setNotice(message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function download(id: number) {
    try {
      const r = await fetch(`/api/documents/${id}/download`, {
        headers: { Authorization: "Bearer " + token },
      });
      if (!r.ok) throw new Error("Download failed");
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = `resume-${id}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  if (!token)
    return (
      <main className="login">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setError("");
            setToken(input);
          }}
        >
          <span className="logo">A</span>
          <h1>Your next chapter starts here.</h1>
          <p>Connect to your private AutoApply workspace.</p>
          {error && <div className="error" role="alert">{error}</div>}
          <label>
            Workspace token
            <input
              type="password"
              autoComplete="off"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              required
            />
          </label>
          <button>Open workspace →</button>
          <small>Your token stays in memory for this session.</small>
        </form>
      </main>
    );
  const listField = (key: keyof Profile, label: string) =>
    profile && (
      <label key={key}>
        {label}
        <textarea
          value={(profile[key] as string[]).join("\n")}
          onChange={(e) =>
            setProfile({ ...profile, [key]: e.target.value.split("\n") })
          }
        />
        <small>
          One entry per line. Include accurate titles and dates in experience
          entries.
        </small>
      </label>
    );
  return (
    <div className="layout">
      <aside>
        <div className="brand">
          <span className="logo">A</span> AutoApply <b>AI</b>
        </div>
        <small className="workspace">YOUR WORKSPACE</small>
        <nav>
          {[
            "Overview",
            "Jobs",
            "Applications",
            "Profile",
            "Sources",
            "Activity",
            "Settings",
          ].map((n) => (
            <button
              className={page === n ? "active" : ""}
              key={n}
              onClick={() => setPage(n)}
            >
              {n}
            </button>
          ))}
        </nav>
        <div className="aside-bottom">
          <span className="dot" /> Local-first workspace
          <small>Private by design</small>
          <button
            onClick={() => {
              setToken("");
              setInput("");
              setProfile(null);
              setSettings(null);
            }}
          >
            Lock workspace
          </button>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <small>WORKSPACE / {page.toUpperCase()}</small>
            <h1>
              {page === "Overview" ? "A clearer path to your next role." : page}
            </h1>
            <p>
              {page === "Overview"
                ? "Discover opportunities. Understand your fit. Keep every step in view."
                : "Manage your job search with verified information."}
            </p>
          </div>
          <button
            className="danger"
            disabled={busy}
            onClick={() =>
              action(
                async () => setSettings(await api("stop", "POST")),
                "Emergency stop enabled",
              )
            }
          >
            Emergency stop
          </button>
        </header>
        <div className="banner">
          <span className="dot" />
          {overview.emergency_stop
            ? "Emergency stop active"
            : "Dry-run workspace"}
          <span>
            Live application submission is unavailable in this release.
          </span>
        </div>
        {error && (
          <div role="alert" className="error">
            {error}
          </div>
        )}
        {notice && (
          <div role="status" className="notice">
            {notice}
          </div>
        )}
        {page === "Overview" && (
          <>
            <div className="stats">
              {[
                ["Discovered", "discovered"],
                ["Matches ≥65", "matched"],
                ["Prepared applications", "prepared"],
                ["Verified submissions", "submitted"],
              ].map(([title, key]) => (
                <section key={key}>
                  <small>{title}</small>
                  <strong>{overview[key] ?? 0}</strong>
                  <span>All time · your workspace</span>
                </section>
              ))}
            </div>
            <div className="columns">
              <section>
                <h2>Your opportunity pipeline</h2>
                <p>
                  Start with a verified profile, then add employer boards to
                  discover roles.
                </p>
                {[
                  [
                    "01",
                    "Build your profile",
                    "Add the career facts used for matching and resumes.",
                    "Profile",
                  ],
                  [
                    "02",
                    "Choose your sources",
                    "Connect public Greenhouse, Lever and Ashby boards.",
                    "Sources",
                  ],
                  [
                    "03",
                    "Review your matches",
                    "Read the evidence behind every score.",
                    "Jobs",
                  ],
                ].map(([n, t, d, p]) => (
                  <button className="step" key={n} onClick={() => setPage(p)}>
                    <span>{n}</span>
                    <div>
                      <b>{t}</b>
                      <p>{d}</p>
                    </div>
                    <span>→</span>
                  </button>
                ))}
              </section>
              <section>
                <h2>Recent activity</h2>
                {activity.events.length ? (
                  activity.events.slice(0, 6).map((e) => (
                    <div className="event" key={e.id}>
                      <span className="dot" />
                      <div>
                        {e.message}
                        <small>{new Date(e.at).toLocaleString()}</small>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="empty">
                    No activity yet. Add a source to begin.
                  </p>
                )}
              </section>
            </div>
          </>
        )}
        {page === "Jobs" && (
          <>
            <input
              className="search"
              aria-label="Search jobs"
              placeholder="Search by role or employer…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div className="job-list">
              {jobs
                .filter((j) =>
                  (j.title + " " + j.employer)
                    .toLowerCase()
                    .includes(query.toLowerCase()),
                )
                .map((j) => (
                  <section key={j.id}>
                    <div className="job-heading">
                      <div>
                        <small>
                          {j.employer} · {j.location}
                        </small>
                        <h2>{j.title}</h2>
                      </div>
                      <span className="score">
                        {j.match ? `${j.match.score}%` : "Unscored"}
                      </span>
                    </div>
                    {j.expired && <p>Posting no longer listed</p>}
                    {j.match && <p>{j.match.explanation}</p>}
                    <details>
                      <summary>Job description</summary>
                      <p className="description">{j.description}</p>
                    </details>
                    <div className="actions">
                      <a href={j.url} target="_blank" rel="noreferrer">
                        Open posting ↗
                      </a>
                      <button
                        disabled={busy || j.expired}
                        onClick={() =>
                          action(
                            () => api(`jobs/${j.id}/score`, "POST"),
                            "Matching queued",
                          )
                        }
                      >
                        Evaluate fit
                      </button>
                      <button
                        disabled={busy || j.expired}
                        onClick={() =>
                          action(
                            () => api(`jobs/${j.id}/prepare`, "POST"),
                            "Resume preparation queued",
                          )
                        }
                      >
                        Prepare resume
                      </button>
                      <button disabled={busy || j.expired} onClick={() => action(
                        () => api(`jobs/${j.id}/dry-run`, "POST"),
                        "Browser dry run queued. It will pause for review without submitting.",
                      )}>Inspect form</button>
                    </div>
                  </section>
                ))}
              {!jobs.length && (
                <section className="empty">
                  No jobs discovered yet. Configure a source to get started.
                </section>
              )}
            </div>
          </>
        )}
        {page === "Profile" && profile && (
          <form
            className="editor"
            onSubmit={(e) => {
              e.preventDefault();
              action(() => api("profile", "PUT", profile), "Profile saved");
            }}
          >
            <section>
              <h2>Verified career profile</h2>
              <p>
                Only include facts you can substantiate. These entries are used
                verbatim in your resume.
              </p>
              <div className="fields">
                {(["name", "email", "phone", "location"] as const).map((k) => (
                  <label key={k}>
                    {k}
                    <input
                      type={k === "email" ? "email" : "text"}
                      value={profile[k]}
                      onChange={(e) =>
                        setProfile({ ...profile, [k]: e.target.value })
                      }
                    />
                  </label>
                ))}
              </div>
              {listField("skills", "Skills")}
              {listField("experience", "Experience and accomplishments")}
              {listField("education", "Education")}
              {listField("certifications", "Certifications")}
              {listField("preferred_titles", "Preferred titles")}
              {listField("allowed_locations", "Allowed locations")}
              {listField(
                "authorized_countries",
                "Countries with work authorization",
              )}
              <label>
                Minimum annual salary
                <input
                  type="number"
                  min="0"
                  value={profile.minimum_salary ?? ""}
                  onChange={(e) =>
                    setProfile({
                      ...profile,
                      minimum_salary: e.target.value
                        ? Number(e.target.value)
                        : null,
                    })
                  }
                />
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={profile.verified}
                  onChange={(e) =>
                    setProfile({ ...profile, verified: e.target.checked })
                  }
                />
                I have verified the accuracy of this profile.
              </label>
              <button disabled={busy}>Save profile</button>
            </section>
          </form>
        )}
        {page === "Sources" && (
          <>
            <section>
              <h2>Add an employer board</h2>
              <form
                className="source-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  action(() => api("boards", "POST", board), "Source added");
                }}
              >
                <label>
                  Platform
                  <select
                    value={board.provider}
                    onChange={(e) =>
                      setBoard({ ...board, provider: e.target.value })
                    }
                  >
                    {["greenhouse", "lever", "ashby"].map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Board slug
                  <input
                    required
                    pattern="[A-Za-z0-9_-]+"
                    placeholder="Employer board identifier"
                    value={board.slug}
                    onChange={(e) =>
                      setBoard({ ...board, slug: e.target.value })
                    }
                  />
                </label>
                <label>
                  Employer name
                  <input
                    required
                    value={board.employer}
                    onChange={(e) =>
                      setBoard({ ...board, employer: e.target.value })
                    }
                  />
                </label>
                <button disabled={busy}>Add source</button>
              </form>
              <p>
                Use the employer identifier from their public ATS board URL.
              </p>
            </section>
            <section>
              <h2>Connected sources</h2>
              {boards.map((b) => (
                <div className="source" key={b.id}>
                  <div>
                    <b>{b.employer}</b>
                    <small>
                      {b.provider} / {b.slug}
                    </small>
                  </div>
                  <button
                    disabled={busy}
                    onClick={() =>
                      action(
                        () => api(`boards/${b.id}/discover`, "POST"),
                        "Discovery queued",
                      )
                    }
                  >
                    Discover now
                  </button>
                </div>
              ))}
              {!boards.length && <p className="empty">No sources connected.</p>}
            </section>
          </>
        )}
        {page === "Applications" && (
          <section>
            <h2>Prepared applications</h2>
            <p>
              Review generated documents before using them on employer websites.
            </p>
            {apps.map((a) => (
              <div className="source" key={a.id}>
                <div>
                  <b>
                    {jobs.find((j) => j.id === a.job_id)?.title ??
                      `Job ${a.job_id}`}
                  </b>
                  <small>{a.status.replaceAll("_", " ")}</small>
                </div>
                <div>
                  {docs
                    .filter((d) => d.job_id === a.job_id)
                    .map((d) => (
                      <button key={d.id} onClick={() => download(d.id)}>
                        Resume v{d.id} ↓
                      </button>
                    ))}
                </div>
              </div>
            ))}
            {!apps.length && (
              <p className="empty">
                Prepare a resume from a job to start tracking it.
              </p>
            )}
          </section>
        )}
        {page === "Activity" && (
          <section>
            <h2>Background tasks</h2>
            {activity.tasks.map((t) => (
              <div className="source" key={t.id}>
                <b>
                  #{t.id} · {t.kind}
                </b>
                <span>
                  {t.status}
                  {t.error ? ` · ${t.error}` : ""}
                </span>
              </div>
            ))}
            {!activity.tasks.length && (
              <p className="empty">Your queue is empty.</p>
            )}
          </section>
        )}
        {page === "Settings" && settings && (
          <form
            className="editor"
            onSubmit={(e) => {
              e.preventDefault();
              action(() => api("settings", "PUT", settings), "Settings saved");
            }}
          >
            <section>
              <h2>Discovery and evaluation</h2>
              <label className="check">
                <input
                  type="checkbox"
                  checked={settings.enabled}
                  onChange={(e) =>
                    setSettings({ ...settings, enabled: e.target.checked })
                  }
                />
                Enable scheduled discovery and matching
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={settings.emergency_stop}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      emergency_stop: e.target.checked,
                    })
                  }
                />
                Emergency stop
              </label>
              {(
                ["minimum_score", "review_score", "interval_hours"] as const
              ).map((k) => (
                <label key={k}>
                  {k.replaceAll("_", " ")}
                  <input
                    type="number"
                    min={k === "interval_hours" ? 1 : 0}
                    max={k === "interval_hours" ? 168 : 100}
                    value={settings[k]}
                    onChange={(e) =>
                      setSettings({ ...settings, [k]: Number(e.target.value) })
                    }
                  />
                </label>
              ))}
              <label>
                Authorized ATS hosts for browser dry runs
                <textarea value={settings.allowed_hosts.join("\n")} onChange={(e) =>
                  setSettings({...settings, allowed_hosts:e.target.value.split("\n").map(x=>x.trim()).filter(Boolean)})
                } />
                <small>One exact supported hostname per line. Add only websites where you authorize automated inspection.</small>
              </label>
              <label>
                Blocked employers
                <textarea
                  value={settings.blocked_employers.join("\n")}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      blocked_employers: e.target.value.split("\n"),
                    })
                  }
                />
              </label>
              <p>
                Submission controls will become available after adapter
                validation. Dry run is enforced.
              </p>
              <button disabled={busy}>Save settings</button>
            </section>
          </form>
        )}
        <footer>AutoApply AI · Your career, your control.</footer>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
