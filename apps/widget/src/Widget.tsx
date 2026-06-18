import { AnimatePresence, LazyMotion, domAnimation, m } from "framer-motion";
import {
  AiRobot,
  Admission,
} from "./icons";
import {
  ArrowUp,
  BookOpen,
  Building2,
  Check,
  ChevronDown,
  Clipboard,
  Copy,
  GraduationCap,
  Languages,
  MapPin,
  Maximize2,
  MessageCircle,
  Minus,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  TrainFront,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import { sendFeedback, sendMessage } from "./api";
import "./i18n";
import { initialLanguage, persistLanguage } from "./i18n";
import { clearSession, loadSession, saveSession } from "./storage";
import type { ChatMessage, Language, WidgetConfig } from "./types";

const actions = [
  ["admissions", Admission],
  ["courses", GraduationCap],
  ["placements", Clipboard],
  ["hostel", Building2],
  ["transport", TrainFront],
  ["scholarships", BookOpen],
  ["departments", GraduationCap],
  ["events", Sparkles],
  ["contact", MapPin],
] as const;

const starterKeys = ["courses", "admissions", "hostel"] as const;
type ErrorKey = "connection" | "feedback";

function createWelcome(content: string): ChatMessage {
  return {
    id: "welcome",
    role: "assistant",
    content,
    created_at: new Date().toISOString(),
    confidence: "verified",
  };
}

function uniqueMessages(items: ChatMessage[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

export function Widget({ config }: { config: WidgetConfig }) {
  const { t, i18n } = useTranslation();
  const widgetPosition = "bottom-right";
  const saved = useMemo(loadSession, []);
  const [open, setOpen] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [language, setLanguage] = useState<Language>(() => initialLanguage());
  const [messages, setMessages] = useState<ChatMessage[]>(
    saved.messages.length ? uniqueMessages(saved.messages) : [createWelcome(t("welcome.message"))],
  );
  const [conversationId, setConversationId] = useState<string | null>(
    saved.conversationId,
  );
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ErrorKey | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [size, setSize] = useState({ width: 420, height: 720 });
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const resizeRef = useRef<{ x: number; y: number; width: number; height: number } | undefined>(undefined);

  useEffect(() => {
    void i18n.changeLanguage(language);
    persistLanguage(language);
    setMessages((current) => {
      if (current.length === 1 && current[0]?.id === "welcome") {
        return [createWelcome(i18n.getFixedT(language)("welcome.message"))];
      }
      return current;
    });
  }, [i18n, language]);

  useEffect(() => {
    saveSession({ conversationId, messages });
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversationId, messages, loading]);

  useEffect(() => {
    const field = inputRef.current;
    if (!field) return;
    field.style.height = "auto";
    field.style.height = `${Math.min(field.scrollHeight, 112)}px`;
  }, [input]);

  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      if (!resizeRef.current) return;
      const deltaX = resizeRef.current.x - event.clientX;
      const deltaY = resizeRef.current.y - event.clientY;
      setSize({
        width: Math.min(620, Math.max(360, resizeRef.current.width + deltaX)),
        height: Math.min(
          window.innerHeight - 40,
          Math.max(560, resizeRef.current.height + deltaY),
        ),
      });
    };
    const onUp = () => {
      resizeRef.current = undefined;
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, []);

  const submit = async (text = input, replacementIndex?: number) => {
    const value = text.trim();
    if (!value || loading) return;
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: value,
      created_at: new Date().toISOString(),
    };
    const next = uniqueMessages(
      replacementIndex === undefined
        ? [...messages, userMessage]
        : [...messages.slice(0, Math.max(0, replacementIndex)), userMessage],
    );
    setMessages(next);
    setInput("");
    setError(null);
    setLoading(true);
    try {
      const response = await sendMessage(
        config,
        value,
        language,
        conversationId,
        next,
      );
      setConversationId(response.conversation_id);
      setMessages((current) => uniqueMessages([...current, response.message]));
    } catch {
      setError("connection");
    } finally {
      setLoading(false);
    }
  };

  const clear = () => {
    clearSession();
    setConversationId(null);
    setMessages([createWelcome(t("welcome.message"))]);
    setError(null);
  };

  const copy = async (message: ChatMessage) => {
    await navigator.clipboard.writeText(message.content);
    setCopied(message.id);
    window.setTimeout(() => setCopied(null), 1200);
  };

  const feedback = async (message: ChatMessage, rating: "up" | "down") => {
    setMessages((current) =>
      current.map((item) => (item.id === message.id ? { ...item, feedback: rating } : item)),
    );
    try {
      await sendFeedback(config, message.id, rating);
    } catch {
      setError("feedback");
    }
  };

  return (
    <LazyMotion features={domAnimation}>
      <div className={`ciet-widget ciet-widget--${widgetPosition}`}>
      <AnimatePresence>
        {!open && (
          <m.div
            className="ciet-launch-wrap"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9 }}
          >
            <span className="ciet-tooltip">{t("launcher.tooltip")}</span>
            <button className="ciet-launcher" onClick={() => setOpen(true)} aria-label={t("launcher.open")}>
              <span className="ciet-pulse" />
              <AiRobot className="ciet-launch-logo" />
              <Sparkles className="ciet-launch-spark" size={13} />
            </button>
          </m.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {open && (
          <m.section
            className={`ciet-panel ${minimized ? "ciet-panel--minimized" : ""}`}
            style={
              {
                "--ciet-width": `${size.width}px`,
                "--ciet-height": `${size.height}px`,
                "--ciet-primary": config.primaryColor ?? "#174f43",
              } as CSSProperties
            }
            role="dialog"
            aria-label={t("header.dialog")}
            initial={{ opacity: 0, y: 18, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.97 }}
          >
            {!minimized && (
              <button
                className="ciet-resizer"
                aria-label={t("header.resize")}
                onPointerDown={(event) => {
                  resizeRef.current = {
                    x: event.clientX,
                    y: event.clientY,
                    width: size.width,
                    height: size.height,
                  };
                }}
              >
                <Maximize2 size={12} />
              </button>
            )}
            <header className="ciet-header">
              <div className="ciet-identity">
                {config.logoUrl ? (
                  <img src={config.logoUrl} alt={t("brand.logoAlt")} />
                ) : (
                  <span className="ciet-bot-mark"><AiRobot /></span>
                )}
                <div>
                  <strong>{t("brand.title")}</strong>
                  <small><i /> {t("brand.subtitle")}</small>
                </div>
              </div>
              <div className="ciet-header-actions">
                {!minimized && (
                  <label className="ciet-language">
                    <Languages size={14} />
                    <select value={language} onChange={(event) => setLanguage(event.target.value as Language)} aria-label={t("header.language")}>
                      <option value="en">{t("language.en")}</option>
                      <option value="te">{t("language.te")}</option>
                      <option value="hi">{t("language.hi")}</option>
                    </select>
                    <ChevronDown size={11} />
                  </label>
                )}
                <button onClick={() => setMinimized(!minimized)} aria-label={minimized ? t("header.restore") : t("header.minimize")}>
                  {minimized ? <MessageCircle size={17} /> : <Minus size={18} />}
                </button>
                <button onClick={() => { setOpen(false); setMinimized(false); }} aria-label={t("header.close")}>
                  <X size={18} />
                </button>
              </div>
            </header>

            {!minimized && (
              <>
                <div className="ciet-trust"><ShieldCheck size={14} /> {t("trust")}</div>
                <div className="ciet-messages" aria-live="polite">
                  {messages.map((message, index) => (
                    <m.article
                      key={message.id}
                      className={`ciet-message-row ciet-message-row--${message.role}`}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.18 }}
                    >
                      {message.role === "assistant" && <span className="ciet-avatar"><Sparkles size={13} /></span>}
                      <div className="ciet-message-wrap">
                        <div className={`ciet-message ciet-message--${message.role}`}>{message.content}</div>
                        <div className="ciet-message-meta">
                          <time>{new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time>
                          {message.confidence && <span className={`ciet-confidence ciet-confidence--${message.confidence}`}>{t(`confidence.${message.confidence}`)}</span>}
                        </div>
                        {message.citations?.length ? (
                          <div className="ciet-citations">
                            {message.citations.map((citation, citationIndex) => (
                              <a href={citation.url} target="_blank" rel="noreferrer" key={`${citation.title}-${citationIndex}`}>
                                <BookOpen size={12} />
                                <span>{citation.title}{citation.section ? ` · ${citation.section}` : ""}</span>
                              </a>
                            ))}
                          </div>
                        ) : null}
                        {message.role === "assistant" && message.id !== "welcome" && (
                          <div className="ciet-message-actions">
                            <button onClick={() => copy(message)} aria-label={copied === message.id ? t("messageActions.copied") : t("messageActions.copy")}>{copied === message.id ? <Check size={13} /> : <Copy size={13} />}</button>
                            <button onClick={() => submit(messages[index - 1]?.content ?? "", index - 1)} aria-label={t("messageActions.regenerate")}><RefreshCw size={13} /></button>
                            <span />
                            <button className={message.feedback === "up" ? "active" : ""} onClick={() => feedback(message, "up")} aria-label={t("messageActions.helpful")}><ThumbsUp size={13} /></button>
                            <button className={message.feedback === "down" ? "active" : ""} onClick={() => feedback(message, "down")} aria-label={t("messageActions.unhelpful")}><ThumbsDown size={13} /></button>
                          </div>
                        )}
                      </div>
                    </m.article>
                  ))}
                  {loading && (
                    <div className="ciet-message-row">
                      <span className="ciet-avatar"><Sparkles size={13} /></span>
                      <div className="ciet-typing" aria-label={t("chat.loading")}><i /><i /><i /></div>
                    </div>
                  )}
                  {error && <div className="ciet-error">{t(`errors.${error}`)}</div>}
                  <div ref={endRef} />
                </div>

                {messages.length <= 1 && (
                  <div className="ciet-starters">
                    <strong>{t("starters.title")}</strong>
                    <div>{starterKeys.map((key) => {
                      const prompt = t(`starters.${key}`);
                      return <button key={key} onClick={() => submit(prompt)}>{prompt}</button>;
                    })}</div>
                  </div>
                )}

                <div className="ciet-quick-actions">
                  {actions.map(([key, Icon]) => <button key={key} onClick={() => submit(t(`actions.${key}.prompt`))}><Icon size={14} />{t(`actions.${key}.label`)}</button>)}
                </div>
                <form className="ciet-composer" onSubmit={(event: FormEvent) => { event.preventDefault(); void submit(); }}>
                  <textarea ref={inputRef} value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      void submit();
                    }
                  }} rows={1} placeholder={t("chat.placeholder")} aria-label={t("chat.messageAria")} />
                  <button type="submit" disabled={!input.trim() || loading} aria-label={t("chat.send")}>
                    {loading ? <RefreshCw className="ciet-send-loading" size={16} /> : <ArrowUp size={18} />}
                  </button>
                </form>
                <footer className="ciet-footer">
                  <button onClick={clear}><RotateCcw size={11} /> {t("footer.clear")}</button>
                  <span>{t("footer.note")}</span>
                  {config.privacyUrl && <a href={config.privacyUrl} target="_blank" rel="noreferrer">{t("footer.privacy")}</a>}
                </footer>
              </>
            )}
          </m.section>
        )}
      </AnimatePresence>
      </div>
    </LazyMotion>
  );
}
