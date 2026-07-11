import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BarChart3,
  BookOpen,
  Database,
  FileText,
  Lock,
  LogOut,
  MessageSquareWarning,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import { client, Document, FAQ, getToken, logout, Metric, setToken, type Analytics } from "./api";
import { CietLogo } from "./CietLogo";
import "./styles.css";

type View = "dashboard" | "documents" | "faqs" | "metrics" | "conversations" | "feedback";

function App() {
  const [authed, setAuthed] = useState(Boolean(getToken()));
  if (!authed) return <Login onLogin={() => setAuthed(true)} />;
  return <Shell onLogout={() => { logout(); setAuthed(false); }} />;
}

function Login({ onLogin }: { onLogin: () => void }) {
  const [email, setEmail] = useState("admin@ciet.edu");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const submit = async (bootstrap = false) => {
    setError("");
    try {
      const result = bootstrap ? await client.bootstrap(email, password) : await client.login(email, password);
      setToken(result.access_token);
      onLogin();
    } catch {
      setError("Login failed. Use Bootstrap only for the first admin account.");
    }
  };
  return (
    <main className="login">
      <section>
        <div className="mark"><CietLogo /></div>
        <h1>CIET AI Admin</h1>
        <p>Secure management console for knowledge, analytics, feedback, and conversation quality.</p>
        <label>Email<input value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <strong className="error">{error}</strong>}
        <button onClick={() => submit()}><Lock size={16} /> Sign in</button>
        <button className="ghost" onClick={() => submit(true)}>Bootstrap first admin</button>
      </section>
    </main>
  );
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
  ];
  return (
    <div className="shell">
      <aside>
        <div className="brand"><CietLogo className="brand-logo" /><div><strong>CIET AI</strong><small>Admin Console</small></div></div>
        <nav>{nav.map(([id, Icon, label]) => <button className={view === id ? "active" : ""} onClick={() => setView(id)} key={id}><Icon size={18} />{label}</button>)}</nav>
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
      </main>
    </div>
  );
}

function Dashboard() {
  const [analytics, setAnalytics] = useState<Analytics>();
  useEffect(() => { void client.analytics().then(setAnalytics); }, []);
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
  const load = () => client.documents().then(setDocs);
  useEffect(() => { void load(); }, []);
  const upload = async (file?: File) => {
    if (!file) return;
    setBusy(true);
    await client.upload(file);
    await load();
    setBusy(false);
  };
  const deleteDoc = async (id: string) => {
    if (confirm("Are you sure you want to delete this document?")) {
      await client.deleteDocument(id);
      await load();
    }
  };
  const reprocessDoc = async (id: string) => {
    await client.reprocessDocument(id);
    await load();
  };
  return (
    <Card title="Document Upload">
      <div className="toolbar">
        <label className="upload">
          <UploadCloud /> Upload PDF, DOCX, XLSX, CSV
          <input type="file" hidden accept=".pdf,.docx,.xlsx,.csv,.txt,.md" onChange={(e) => void upload(e.target.files?.[0])} />
        </label>
        <button onClick={() => client.refreshKnowledge()}><RefreshCw size={15} /> Refresh Knowledge</button>
      </div>
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
  const load = () => client.faqs().then(setItems);
  useEffect(() => { void load(); }, []);
  const save = async () => { await client.createFaq({ question, answer, language: "en", source: "Verified FAQ", is_active: true }); setQuestion(""); setAnswer(""); await load(); };
  const deleteFaq = async (id: string) => {
    if (confirm("Are you sure you want to delete this FAQ?")) {
      await client.deleteFaq(id);
      await load();
    }
  };
  return <Card title="FAQ Management"><Form question={question} answer={answer} setQuestion={setQuestion} setAnswer={setAnswer} save={save} /><Table rows={items.map((i) => [i.question, i.language, i.source, new Date(i.updated_at).toLocaleDateString(), <button key={i.id} onClick={() => void deleteFaq(i.id)} style={{ padding: "4px 8px", fontSize: "11px", borderRadius: "6px", height: "auto", background: "#d32f2f", color: "white", border: 0 }}>Delete</button>])} empty="No FAQs yet." /></Card>;
}

function Metrics() {
  const [items, setItems] = useState<Metric[]>([]);
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const load = () => client.metrics().then(setItems);
  useEffect(() => { void load(); }, []);
  const save = async () => { await client.createMetric({ name, value, verified_by: "Admin", source: "Verified Metrics", is_sensitive_stat: true }); setName(""); setValue(""); await load(); };
  const deleteMetric = async (id: string) => {
    if (confirm("Are you sure you want to delete this Metric?")) {
      await client.deleteMetric(id);
      await load();
    }
  };
  return <Card title="Metrics Management"><div className="form"><input placeholder="Metric name" value={name} onChange={(e) => setName(e.target.value)} /><input placeholder="Verified value" value={value} onChange={(e) => setValue(e.target.value)} /><button onClick={save}><Plus size={15} /> Add Metric</button></div><Table rows={items.map((i) => [i.name, i.value, i.verified_by, new Date(i.updated_at).toLocaleDateString(), <button key={i.id} onClick={() => void deleteMetric(i.id)} style={{ padding: "4px 8px", fontSize: "11px", borderRadius: "6px", height: "auto", background: "#d32f2f", color: "white", border: 0 }}>Delete</button>])} empty="No metrics yet." /></Card>;
}

function Logs() {
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  useEffect(() => { void client.conversations().then(setRows); }, []);
  return <Card title="Conversation Logs & Failed Query Analysis"><div className="search"><Search size={16} /> Review low-confidence and fallback conversations first.</div><Table rows={rows.map((r) => [String(r.role), String(r.content).slice(0, 80), String(r.confidence ?? "-"), String(r.route ?? "-")])} empty="No logs yet." /></Card>;
}

function Feedback() {
  return <Card title="Feedback Dashboard"><p>Feedback events are captured through `/api/v1/feedback` and reflected in satisfaction analytics. Connect this panel to the feedback export when volume grows.</p></Card>;
}

function Form({ question, answer, setQuestion, setAnswer, save }: { question: string; answer: string; setQuestion: (v: string) => void; setAnswer: (v: string) => void; save: () => Promise<void> }) {
  return <div className="form"><input placeholder="Verified question" value={question} onChange={(e) => setQuestion(e.target.value)} /><input placeholder="Verified answer" value={answer} onChange={(e) => setAnswer(e.target.value)} /><button onClick={save}><Plus size={15} /> Add FAQ</button></div>;
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="card"><h2>{title}</h2>{children}</section>;
}

function Stat({ label, value, icon: Icon }: { label: string; value: string | number; icon: typeof Activity }) {
  return <section className="stat"><Icon /><span>{label}</span><strong>{value}</strong></section>;
}

function Table({ rows, empty }: { rows: React.ReactNode[][]; empty: string }) {
  if (!rows.length) return <p className="empty">{empty}</p>;
  return <div className="table">{rows.map((row, index) => <div key={index} style={{ gridTemplateColumns: `repeat(${row.length}, minmax(0, 1fr))` }}>{row.map((cell, cellIndex) => <span key={cellIndex}>{cell}</span>)}</div>)}</div>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
