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
import { ApiError, sendFeedback, sendMessage } from "./api";
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
type NoticeKey = "feedbackSaved";
const languageOptions: Language[] = ["en", "te", "hi"];

function createWelcome(content: string, language: Language): ChatMessage {
  return {
    id: "welcome",
    role: "assistant",
    content,
    language,
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

function displayLanguage(message: ChatMessage): Language {
  if (message.language) return message.language;
  // Sessions saved by older widget versions lacked message language. This is a
  // display-only migration path; new messages carry the API/client language.
  if (/[ఀ-౿]/u.test(message.content)) return "te";
  if (/[ऀ-ॿ]/u.test(message.content)) return "hi";
  return "en";
}

function LanguageSelector({ language, onChange }: { language: Language; onChange: (language: Language) => void }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!expanded) return;
    const closeOnOutsidePointer = (event: PointerEvent) => {
      if (!event.composedPath().includes(menuRef.current as EventTarget)) setExpanded(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false);
    };
    document.addEventListener("pointerdown", closeOnOutsidePointer);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsidePointer);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [expanded]);

  return (
    <div className="ciet-language" ref={menuRef}>
      <button
        className="ciet-language-trigger"
        type="button"
        aria-label={t("header.language")}
        aria-haspopup="menu"
        aria-expanded={expanded}
        aria-controls="ciet-language-menu"
        onClick={() => setExpanded((current) => !current)}
      >
        <Languages size={14} />
        <span lang={language}>{t(`language.${language}`)}</span>
        <ChevronDown className={expanded ? "ciet-language-chevron--open" : undefined} size={14} />
      </button>
      {expanded && (
        <div id="ciet-language-menu" className="ciet-language-menu" role="menu" aria-label={t("header.language")}>
          {languageOptions.map((option) => (
            <button
              key={option}
              className="ciet-language-option"
              type="button"
              role="menuitemradio"
              aria-checked={option === language}
              lang={option}
              data-language={option}
              onClick={() => {
                onChange(option);
                setExpanded(false);
              }}
            >
              <span>{t(`language.${option}`)}</span>
              {option === language && <Check size={14} aria-hidden="true" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Widget({ config }: { config: WidgetConfig }) {
  const { t, i18n } = useTranslation();
  const widgetPosition = config.position;
  const saved = useMemo(loadSession, []);
  const [open, setOpen] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [language, setLanguage] = useState<Language>(() => initialLanguage());
  const [messages, setMessages] = useState<ChatMessage[]>(
    saved.messages.length ? uniqueMessages(saved.messages) : [createWelcome(t("welcome.message"), language)],
  );
  const [conversationId, setConversationId] = useState<string | null>(
    saved.conversationId,
  );
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeKey | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [size, setSize] = useState({ width: 420, height: 720 });
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const launcherRef = useRef<HTMLButtonElement>(null);
  const resizeRef = useRef<{ x: number; y: number; width: number; height: number } | undefined>(undefined);

  useEffect(() => {
    const openWidget = () => { setOpen(true); setMinimized(false); };
    window.addEventListener("ciet-ai:open", openWidget);
    return () => window.removeEventListener("ciet-ai:open", openWidget);
  }, []);

  useEffect(() => {
    void i18n.changeLanguage(language);
    persistLanguage(language);
    setMessages((current) => {
      if (current.length === 1 && current[0]?.id === "welcome") {
        return [createWelcome(i18n.getFixedT(language)("welcome.message"), language)];
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
    if (open && !minimized) inputRef.current?.focus();
  }, [open, minimized]);

  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      setMinimized(false);
      window.requestAnimationFrame(() => launcherRef.current?.focus());
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  const closeWidget = () => {
    setOpen(false);
    setMinimized(false);
    window.requestAnimationFrame(() => launcherRef.current?.focus());
  };

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
      language,
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
      const responseLanguage = language;
      const response = await sendMessage(
        config,
        value,
        responseLanguage,
        conversationId,
      );
      setConversationId(response.conversation_id);
      setMessages((current) => uniqueMessages([...current, { ...response.message, language: response.message.language ?? responseLanguage }]));
    } catch (caught) {
      if (caught instanceof ApiError) {
        if (caught.status === 408) setError(t("errors.timeout"));
        else if (caught.status === 401) setError(t("errors.unauthorized"));
        else if (caught.status === 403) setError(t("errors.forbidden"));
        else if (caught.status === 404) setError(t("errors.notFound"));
        else if (caught.status === 409) setError(t("errors.conflict"));
        else if (caught.status === 422) setError(t("errors.invalidRequest"));
        else if (caught.status === 429) setError(t("errors.rateLimit"));
        else if ([500, 502, 503].includes(caught.status)) setError(t("errors.server"));
        else if (caught.status >= 500) setError(t("errors.server"));
        else if (caught.status === 0) setError(t("errors.connection"));
        else setError(caught.message);
      } else {
        setError(t("errors.connection"));
      }
    } finally {
      setLoading(false);
    }
  };

  const clear = () => {
    clearSession();
    setConversationId(null);
    setMessages([createWelcome(t("welcome.message"), language)]);
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
      setNotice("feedbackSaved");
      window.setTimeout(() => setNotice(null), 2200);
    } catch {
      setMessages((current) =>
        current.map((item) => (item.id === message.id ? { ...item, feedback: undefined } : item)),
      );
      setError(t("errors.feedback"));
    }
  };

  return (
    <div className={`ciet-widget ciet-widget--${widgetPosition}`} lang={language}>
        {!open && (
          <div className="ciet-launch-wrap">
            <span className="ciet-tooltip">{t("launcher.tooltip")}</span>
            <button ref={launcherRef} className="ciet-launcher" onClick={() => setOpen(true)} aria-label={t("launcher.open")}>
              <span className="ciet-pulse" />
              <AiRobot className="ciet-launch-logo" />
              <Sparkles className="ciet-launch-spark" size={13} />
            </button>
          </div>
        )}

        {open && (
          <section
            className={`ciet-panel ${minimized ? "ciet-panel--minimized" : ""}`}
            style={
              {
                "--ciet-width": `${size.width}px`,
                "--ciet-height": `${size.height}px`,
                "--ciet-primary": config.primaryColor ?? "#174f43",
              } as CSSProperties
            }
            role="dialog"
            aria-modal="false"
            aria-label={t("header.dialog")}
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
                  <LanguageSelector language={language} onChange={setLanguage} />
                )}
                <button onClick={() => setMinimized(!minimized)} aria-label={minimized ? t("header.restore") : t("header.minimize")}>
                  {minimized ? <MessageCircle size={17} /> : <Minus size={18} />}
                </button>
                <button onClick={closeWidget} aria-label={t("header.close")}>
                  <X size={18} />
                </button>
              </div>
            </header>

            {!minimized && (
              <>
                <div className="ciet-trust">
                  <ShieldCheck size={14} />
                  <span>{t("trust")}</span>
                  <i aria-hidden="true" />
                  <span className="ciet-trust-secondary">{t("brand.subtitle")}</span>
                </div>
                <div className="ciet-messages" aria-live="polite" aria-label={t("chat.history")} tabIndex={0}>
                  {messages.map((message, index) => (
                    <article
                      key={message.id}
                      className={`ciet-message-row ciet-message-row--${message.role}`}
                      lang={displayLanguage(message)}
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
                            {message.citations.map((citation, citationIndex) => citation.url ? (
                              <a href={citation.url} target="_blank" rel="noreferrer" key={`${citation.title}-${citationIndex}`}>
                                <BookOpen size={12} />
                                <span>{citation.title}{citation.section ? ` · ${citation.section}` : ""}</span>
                              </a>
                            ) : (
                              <span className="ciet-citation" key={`${citation.title}-${citationIndex}`}>
                                <BookOpen size={12} />
                                <span>{citation.title}{citation.section ? ` · ${citation.section}` : ""}</span>
                              </span>
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
                    </article>
                  ))}
                  {loading && (
                    <div className="ciet-message-row">
                      <span className="ciet-avatar"><Sparkles size={13} /></span>
                      <div className="ciet-typing" aria-label={t("chat.loading")}><i /><i /><i /></div>
                    </div>
                  )}
                  {error && <div className="ciet-error">{error}</div>}
                  {notice && <div className="ciet-notice" role="status">{t(`notices.${notice}`)}</div>}
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
          </section>
        )}
    </div>
  );
}
