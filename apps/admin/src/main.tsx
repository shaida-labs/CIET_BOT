import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BarChart3,
  BookOpen,
  Database,
  FileText,
  LoaderCircle,
  Lock,
  LogOut,
  MessageSquareWarning,
  Plus,
  Pencil,
  RefreshCw,
  Search,
  ShieldCheck,
  UserPlus,
  UploadCloud,
} from "lucide-react";
import { ApiError, client, Document, FAQ, logout, Metric, type Analytics, type Feedback as FeedbackItem } from "./api";
import { CietLogo } from "./CietLogo";
import "./styles.css";

type View = "dashboard" | "documents" | "faqs" | "metrics" | "conversations" | "feedback" | "administrators";

function App() {
  if (window.location.pathname === "/accept-invitation" || window.location.pathname.endsWith("/accept-invitation")) return <AcceptInvitation />;
  return <AuthenticatedAdmin />;
}

function AuthenticatedAdmin() {
  const [authed, setAuthed] = useState<boolean | undefined>();
  useEffect(() => {
    void client.session().then(() => setAuthed(true)).catch(() => setAuthed(false));
  }, []);
  if (authed === undefined) return <Loading label="Checking your secure session…" />;
  if (!authed) return <Login onLogin={() => setAuthed(true)} />;
  return <Shell onLogout={() => { void logout().finally(() => setAuthed(false)); }} />;
}

function AcceptInvitation() {
  const token = new URLSearchParams(window.location.search).get("token") ?? "";
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const accept = async () => {
    if (!token) {
      setError("This invitation link is missing its token.");
      return;
    }
    if (password !== confirmation) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await client.acceptInvitation({ token, name, password });
      setNotice(result.message);
    } catch (caught) {
      setError(caught instanceof ApiError && caught.status === 400 ? "This invitation is invalid or expired." : "The invitation could not be accepted.");
    } finally {
      setBusy(false);
    }
  };
  return <main className="login"><section><div className="mark"><CietLogo /></div><h1>Accept CIET AI invitation</h1><p>Set your administrator name and a strong password, then sign in to complete email verification.</p><form onSubmit={(event) => { event.preventDefault(); void accept(); }}><label>Full name<input required value={name} onChange={(event) => setName(event.target.value)} /></label><label>Password<input required minLength={12} type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label><label>Confirm password<input required minLength={12} type="password" autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label>{error && <strong className="error" role="alert">{error}</strong>}{notice && <strong className="success" role="status">{notice}</strong>}<button type="submit" disabled={busy}>{busy ? "Activating…" : "Activate administrator account"}</button></form></section></main>;
}

function Login({ onLogin }: { onLogin: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [challenge, setChallenge] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [resendIn, setResendIn] = useState(0);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!resendIn) return;
    const timer = window.setInterval(() => setResendIn((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [resendIn]);
  const submit = async () => {
    setError("");
    try {
      const result = await client.login(email, password);
      if (!result.challenge) throw new Error("The verification challenge was not created.");
      setChallenge(result.challenge);
      setResendIn(60);
    } catch (caught) {
      setError(loginErrorMessage(caught));
    }
  };
  const verify = async () => {
    if (!challenge || code.length !== 6) return;
    setError("");
    try {
      await client.verifyOtp(challenge, code);
      onLogin();
    } catch (caught) {
      setError(loginErrorMessage(caught, "otp"));
    }
  };
  const resend = async () => {
    if (!challenge || resendIn) return;
    setError("");
    try {
      const result = await client.resendOtp(challenge);
      if (result.challenge) setChallenge(result.challenge);
      setCode("");
      setResendIn(60);
    } catch (caught) {
      setError(loginErrorMessage(caught));
    }
  };
  if (challenge) {
    return (
      <main className="login">
        <section>
          <div className="mark"><CietLogo /></div>
          <h1>Verify your email</h1>
          <p>A six-digit verification code was sent to {maskEmail(email)}.</p>
          <form onSubmit={(event) => { event.preventDefault(); void verify(); }}>
            <label htmlFor="admin-otp">Verification code</label>
            <input
              id="admin-otp"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              maxLength={6}
              aria-label="Six-digit verification code"
              value={code}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
              autoFocus
            />
            {error && <strong className="error" role="alert">{error}</strong>}
            <button type="submit" disabled={code.length !== 6}><Lock size={16} /> Verify</button>
            <button type="button" className="ghost" disabled={resendIn > 0} onClick={() => void resend()}>
              {resendIn ? `Resend available in 00:${String(resendIn).padStart(2, "0")}` : "Resend code"}
            </button>
          </form>
        </section>
      </main>
    );
  }
  return (
    <main className="login">
      <section>
        <div className="mark"><CietLogo /></div>
        <h1>CIET AI Admin</h1>
        <p>Secure management console for knowledge, analytics, feedback, and conversation quality.</p>
        <form onSubmit={(event) => { event.preventDefault(); void submit(); }}>
          <label>Email<input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
          <label>Password<input type="password" autoComplete="current-password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
          {error && <strong className="error" role="alert">{error}</strong>}
          <button type="submit"><Lock size={16} /> Sign in</button>
        </form>
      </section>
    </main>
  );
}

function loginErrorMessage(error: unknown, stage: "password" | "otp" = "password") {
  if (error instanceof ApiError) {
    if (error.status === 401) return stage === "otp" ? "Invalid or expired verification code." : "Invalid email or password.";
    if (error.status === 403 && error.message.includes("CSRF")) return "Security validation failed. Refresh the page and try again.";
    if (error.status === 429) return "Too many attempts. Please try again shortly.";
    if (error.status === 503) return "BLOCKED - EXTERNAL CONFIGURATION REQUIRED: email delivery is not configured.";
    if (error.status >= 500) return "The authentication service is temporarily unavailable.";
    return error.message;
  }
  return "Cannot connect to CIET AI. Check that the API is running.";
}

function maskEmail(value: string) {
  const [local, domain] = value.split("@");
  if (!local || !domain) return value;
  return `${local.slice(0, 1)}${"*".repeat(Math.max(1, local.length - 1))}@${domain}`;
}

function Shell({ onLogout }: { onLogout: () => void }) {
  const [view, setView] = useState<View>("dashboard");
  const nav: [View, typeof Activity, string][] = [
    ["dashboard", Activity, "Dashboard"],
    ["documents", FileText, "Documents"],
    ["faqs", BookOpen, "FAQs"],
    ["metrics", Database, "Metrics"],
    ["conversations", MessageSquareWarning, "Logs"],
    ["feedback", ShieldCheck, "Feedback"],
    ["administrators", UserPlus, "Administrators"],
  ];
  return (
    <div className="shell">
      <aside>
        <div className="brand"><CietLogo className="brand-logo" /><div><strong>CIET AI</strong><small>Admin Console</small></div></div>
        <nav aria-label="Admin sections">{nav.map(([id, Icon, label]) => <button className={view === id ? "active" : ""} onClick={() => setView(id)} key={id}><Icon size={18} />{label}</button>)}</nav>
        <button className="logout" onClick={onLogout}><LogOut size={17} /> Logout</button>
      </aside>
      <main>
        <header><div><h1>{nav.find(([id]) => id === view)?.[2]}</h1><p>Production controls for the shared website and WhatsApp assistant.</p></div></header>
        {view === "dashboard" && <Dashboard />}
        {view === "documents" && <Documents />}
        {view === "faqs" && <Faqs />}
        {view === "metrics" && <Metrics />}
        {view === "conversations" && <Logs />}
        {view === "feedback" && <Feedback />}
        {view === "administrators" && <Administrators />}
      </main>
    </div>
  );
}

function Administrators() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("content_admin");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const invite = async () => {
    setBusy(true);
    setNotice("");
    setError("");
    try {
      const result = await client.inviteAdmin({ name, email, role });
      setNotice(result.message);
      setName("");
      setEmail("");
    } catch (caught) {
      setError(caught instanceof ApiError && caught.status === 403 ? "Only an authorized administrator can send invitations." : "Invitation could not be sent.");
    } finally {
      setBusy(false);
    }
  };
  return <Card title="Invite Administrator"><p>New administrators receive a single-use invitation by official email and must set a password before completing email verification.</p><div className="form"><input aria-label="Administrator name" placeholder="Full name" value={name} onChange={(event) => setName(event.target.value)} /><input aria-label="Administrator email" type="email" placeholder="Official email" value={email} onChange={(event) => setEmail(event.target.value)} /><select aria-label="Administrator role" value={role} onChange={(event) => setRole(event.target.value)}><option value="content_admin">Content Manager</option><option value="admissions_admin">HOD / Admissions</option><option value="placement_admin">Placement Manager</option><option value="viewer">Auditor / Viewer</option><option value="admin">Director</option></select><button disabled={busy || !name.trim() || !email.trim()} onClick={() => void invite()}><UserPlus size={15} /> Send invitation</button></div>{notice && <p className="success" role="status">{notice}</p>}{error && <p className="error" role="alert">{error}</p>}</Card>;
}

function Dashboard() {
  const [analytics, setAnalytics] = useState<Analytics>();
  const [error, setError] = useState("");
  useEffect(() => { void client.analytics().then(setAnalytics).catch(() => setError("Dashboard data could not be loaded.")); }, []);
  if (error) return <Card title="Dashboard"><p className="error">{error}</p></Card>;
  if (!analytics) return <Loading label="Loading dashboard analytics…" />;
  return (
    <>
      <section className="stats">
        <Stat label="Total Queries" value={analytics?.total_queries ?? 0} icon={Activity} />
        <Stat label="Failed Queries" value={analytics?.failed_queries ?? 0} icon={MessageSquareWarning} />
        <Stat label="Avg Response" value={`${analytics?.avg_response_ms ?? 0}ms`} icon={BarChart3} />
        <Stat label="Satisfaction" value={`${Math.round((analytics?.user_satisfaction ?? 0) * 100)}%`} icon={ShieldCheck} />
      </section>
      <section className="grid two">
        <Card title="Channel Usage"><div className="split"><b>Website</b><span>{analytics?.website_usage ?? 0}</span></div><div className="split"><b>WhatsApp</b><span>{analytics?.whatsapp_usage ?? 0}</span></div></Card>
        <Card title="Popular Questions">{analytics?.popular_questions.length ? analytics.popular_questions.map((q) => <div className="split" key={q.query}><b>{q.query}</b><span>{q.count}</span></div>) : <p>No query data yet.</p>}</Card>
      </section>
    </>
  );
}

function Documents() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const load = () => client.documents().then(setDocs);
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (!docs.some((item) => ["queued", "extracting", "chunking", "embedding"].includes(item.status))) return;
    const timer = window.setInterval(() => void load(), 2500);
    return () => window.clearInterval(timer);
  }, [docs]);
  const upload = async (file?: File) => {
    if (!file) return;
    setBusy(true);
    try {
      await client.upload(file);
      setNotice("Document uploaded and queued for indexing.");
      await load();
    } finally { setBusy(false); }
  };
  const deleteDoc = async (id: string) => {
    if (confirm("Are you sure you want to delete this document?")) {
      await client.deleteDocument(id);
      setNotice("Document deleted.");
      await load();
    }
  };
  const reprocessDoc = async (id: string) => {
    await client.reprocessDocument(id);
    setNotice("Document queued for reprocessing.");
    await load();
  };
  const refresh = async () => {
    setBusy(true);
    try {
      const result = await client.refreshKnowledge();
      setNotice(`${result.documents} document${result.documents === 1 ? "" : "s"} queued for refresh.`);
      await load();
    } finally { setBusy(false); }
  };
  return (
    <Card title="Document Upload">
      <div className="toolbar">
        <label className="upload">
          <UploadCloud /> Upload PDF, DOCX, XLSX, CSV
          <input type="file" hidden accept=".pdf,.docx,.xlsx,.csv,.txt,.md" onChange={(e) => void upload(e.target.files?.[0])} />
        </label>
        <button disabled={busy} onClick={() => void refresh()}><RefreshCw size={15} /> Refresh Knowledge</button>
      </div>
      {notice && <p className="success" role="status">{notice}</p>}
      <Table
        rows={docs.map((d) => [
          d.title,
          d.mime_type,
          d.status,
          new Date(d.uploaded_at).toLocaleString(),
          <div style={{ display: "flex", gap: "8px" }} key={d.id}>
            <button onClick={() => void reprocessDoc(d.id)} className="ghost" style={{ padding: "4px 8px", fontSize: "11px", borderRadius: "6px", height: "auto", border: "1px solid #174f43", color: "#174f43", background: "#e8f2e6" }}>Reprocess</button>
            <button onClick={() => void deleteDoc(d.id)} style={{ padding: "4px 8px", fontSize: "11px", borderRadius: "6px", height: "auto", background: "#d32f2f", color: "white", border: 0 }}>Delete</button>
          </div>
        ])}
        empty={busy ? "Uploading..." : "No documents uploaded yet."}
      />
    </Card>
  );
}

function Faqs() {
  const [items, setItems] = useState<FAQ[]>([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [language, setLanguage] = useState("en");
  const [source, setSource] = useState("Verified FAQ");
  const [active, setActive] = useState(true);
  const [editing, setEditing] = useState<FAQ | null>(null);
  const [notice, setNotice] = useState("");
  const load = () => client.faqs().then(setItems);
  useEffect(() => { void load(); }, []);
  const reset = () => {
    setEditing(null); setQuestion(""); setAnswer(""); setLanguage("en"); setSource("Verified FAQ"); setActive(true);
  };
  const save = async () => {
    const payload = { question, answer, language, source, is_active: active };
    if (editing) await client.updateFaq(editing.id, payload); else await client.createFaq(payload);
    setNotice(editing ? "FAQ updated." : "FAQ added.");
    reset(); await load();
  };
  const editFaq = (faq: FAQ) => {
    setEditing(faq); setQuestion(faq.question); setAnswer(faq.answer); setLanguage(faq.language); setSource(faq.source); setActive(faq.is_active);
  };
  const deleteFaq = async (id: string) => {
    if (confirm("Are you sure you want to delete this FAQ?")) {
      await client.deleteFaq(id);
      setNotice("FAQ deleted.");
      await load();
    }
  };
  return <Card title="FAQ Management"><div className="form"><input aria-label="Verified FAQ question" placeholder="Verified question" value={question} onChange={(e) => setQuestion(e.target.value)} /><input aria-label="Verified FAQ answer" placeholder="Verified answer" value={answer} onChange={(e) => setAnswer(e.target.value)} /><select aria-label="FAQ language" value={language} onChange={(e) => setLanguage(e.target.value)}><option value="en">English</option><option value="te">Telugu</option><option value="hi">Hindi</option></select><input aria-label="FAQ source" placeholder="Official source" value={source} onChange={(e) => setSource(e.target.value)} /><label className="check"><input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> Active</label><button disabled={!question.trim() || !answer.trim() || !source.trim()} onClick={() => void save()}>{editing ? <Pencil size={15} /> : <Plus size={15} />} {editing ? "Save FAQ" : "Add FAQ"}</button>{editing && <button className="secondary" onClick={reset}>Cancel</button>}</div>{notice && <p className="success" role="status">{notice}</p>}<Table rows={items.map((i) => [i.question, i.language, i.source, i.is_active ? "Active" : "Inactive", new Date(i.updated_at).toLocaleDateString(), <div className="row-actions" key={i.id}><button className="edit" onClick={() => editFaq(i)}><Pencil size={12} /> Edit</button><button className="danger" onClick={() => void deleteFaq(i.id)}>Delete</button></div>])} empty="No FAQs yet." /></Card>;
}

function Metrics() {
  const [items, setItems] = useState<Metric[]>([]);
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const [unit, setUnit] = useState("");
  const [verifiedBy, setVerifiedBy] = useState("");
  const [source, setSource] = useState("");
  const [sensitive, setSensitive] = useState(true);
  const [editing, setEditing] = useState<Metric | null>(null);
  const [notice, setNotice] = useState("");
  const load = () => client.metrics().then(setItems);
  useEffect(() => { void load(); }, []);
  const reset = () => {
    setEditing(null); setName(""); setValue(""); setUnit(""); setVerifiedBy(""); setSource(""); setSensitive(true);
  };
  const save = async () => {
    const payload = { name, value, unit: unit || undefined, verified_by: verifiedBy, source, is_sensitive_stat: sensitive };
    if (editing) await client.updateMetric(editing.id, payload); else await client.createMetric(payload);
    setNotice(editing ? "Metric updated." : "Metric added.");
    reset(); await load();
  };
  const deleteMetric = async (id: string) => {
    if (confirm("Are you sure you want to delete this Metric?")) {
      await client.deleteMetric(id);
      setNotice("Metric deleted.");
      await load();
    }
  };
  return <Card title="Metrics Management"><div className="form"><input aria-label="Metric name" placeholder="Metric name" value={name} onChange={(e) => setName(e.target.value)} /><input aria-label="Verified metric value" placeholder="Verified value" value={value} onChange={(e) => setValue(e.target.value)} /><input aria-label="Metric unit" placeholder="Unit (optional)" value={unit} onChange={(e) => setUnit(e.target.value)} /><input aria-label="Verified by" placeholder="Verified by (for example, Placement Office)" value={verifiedBy} onChange={(e) => setVerifiedBy(e.target.value)} /><input aria-label="Metric source" placeholder="Official source" value={source} onChange={(e) => setSource(e.target.value)} /><label className="check"><input type="checkbox" checked={sensitive} onChange={(e) => setSensitive(e.target.checked)} /> Sensitive official statistic</label><button disabled={!name.trim() || !value.trim() || !verifiedBy.trim() || !source.trim()} onClick={() => void save()}>{editing ? <Pencil size={15} /> : <Plus size={15} />} {editing ? "Save Metric" : "Add Metric"}</button>{editing && <button className="secondary" onClick={reset}>Cancel</button>}</div>{notice && <p className="success" role="status">{notice}</p>}<Table rows={items.map((i) => [i.name, `${i.value}${i.unit ? ` ${i.unit}` : ""}`, i.verified_by, i.source, i.is_sensitive_stat ? "Sensitive" : "General", new Date(i.updated_at).toLocaleDateString(), <div className="row-actions" key={i.id}><button className="edit" onClick={() => { setEditing(i); setName(i.name); setValue(i.value); setUnit(i.unit ?? ""); setVerifiedBy(i.verified_by); setSource(i.source); setSensitive(i.is_sensitive_stat); }}><Pencil size={12} /> Edit</button><button className="danger" onClick={() => void deleteMetric(i.id)}>Delete</button></div>])} empty="No metrics yet." /></Card>;
}

function Logs() {
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  useEffect(() => { void client.conversations().then(setRows); }, []);
  return <Card title="Conversation Logs & Failed Query Analysis"><div className="search"><Search size={16} /> Review low-confidence and fallback conversations first.</div><Table rows={rows.map((r) => [String(r.role), String(r.content).slice(0, 80), String(r.confidence ?? "-"), String(r.route ?? "-")])} empty="No logs yet." /></Card>;
}

function Feedback() {
  const [items, setItems] = useState<FeedbackItem[]>();
  const [error, setError] = useState("");
  useEffect(() => { void client.feedback().then(setItems).catch(() => setError("Feedback could not be loaded.")); }, []);
  if (error) return <Card title="Feedback Dashboard"><p className="error">{error}</p></Card>;
  if (!items) return <Loading label="Loading feedback…" />;
  return <Card title="Feedback Dashboard"><Table rows={items.map((item) => [item.rating === "up" ? "Helpful" : "Needs review", item.message_content, item.comment || "—", new Date(item.created_at).toLocaleString()])} empty="No feedback has been submitted yet." /></Card>;
}

function Loading({ label }: { label: string }) { return <section className="loading" aria-live="polite"><LoaderCircle size={20} /> {label}</section>; }

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="card"><h2>{title}</h2>{children}</section>;
}

function Stat({ label, value, icon: Icon }: { label: string; value: string | number; icon: typeof Activity }) {
  return <section className="stat"><Icon /><span>{label}</span><strong>{value}</strong></section>;
}

function Table({ rows, empty }: { rows: React.ReactNode[][]; empty: string }) {
  if (!rows.length) return <p className="empty">{empty}</p>;
  // tabIndex keeps the vertically scrollable table reachable by keyboard (axe
  // scrollable-region-focusable) now that long logs are capped instead of
  // stretching the document to tens of thousands of pixels.
  return <div className="table" role="table" tabIndex={0}>{rows.map((row, index) => <div role="row" key={index} style={{ gridTemplateColumns: `repeat(${row.length}, minmax(0, 1fr))` }}>{row.map((cell, cellIndex) => <span role="cell" key={cellIndex}>{cell}</span>)}</div>)}</div>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
