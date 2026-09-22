import { Check, Globe, MessageCircle, Users } from "lucide-react";
import { ReactNode } from "react";

interface PreviewPageProps {
  children: ReactNode;
}

export function PreviewPage({ children }: PreviewPageProps) {
  return (
    <div className="ciet-preview-layout">
      <div className="ciet-preview-background" />

      <div className="ciet-preview-content">
        <aside className="ciet-preview-hero">
          <div className="ciet-preview-logo-container">
            <img
              src={`${import.meta.env.BASE_URL}ciet-logo.jpg`}
              alt="CIET Logo"
              className="ciet-preview-brand-logo"
            />
          </div>

          <div className="ciet-preview-hero-text">
            <p className="ciet-preview-welcome">Welcome to</p>
            <h1 className="ciet-preview-title">
              <span className="ciet-preview-title-ciet">CIET</span>
              <span className="ciet-preview-title-ai"> AI Assistant</span>
            </h1>
            <p className="ciet-preview-description">
              Your official AI-powered guide to admissions, academics, placements, campus life and more.
            </p>
          </div>

          <div className="ciet-preview-features">
            <div className="ciet-preview-feature">
              <div className="ciet-preview-feature-icon">
                <Check size={20} />
              </div>
              <div className="ciet-preview-feature-text">
                <div className="ciet-preview-feature-title">Verified Information</div>
                <div className="ciet-preview-feature-description">
                  Answers from official CIET sources
                </div>
              </div>
            </div>

            <div className="ciet-preview-feature">
              <div className="ciet-preview-feature-icon">
                <MessageCircle size={20} />
              </div>
              <div className="ciet-preview-feature-text">
                <div className="ciet-preview-feature-title">Instant Support</div>
                <div className="ciet-preview-feature-description">
                  Get accurate information 24/7
                </div>
              </div>
            </div>

            <div className="ciet-preview-feature">
              <div className="ciet-preview-feature-icon">
                <Globe size={20} />
              </div>
              <div className="ciet-preview-feature-text">
                <div className="ciet-preview-feature-title">Multilingual</div>
                <div className="ciet-preview-feature-description">
                  English • <span lang="te">తెలుగు</span> • <span lang="hi">हिन्दी</span>
                </div>
              </div>
            </div>

            <div className="ciet-preview-feature">
              <div className="ciet-preview-feature-icon">
                <Users size={20} />
              </div>
              <div className="ciet-preview-feature-text">
                <div className="ciet-preview-feature-title">For Everyone</div>
                <div className="ciet-preview-feature-description">
                  Students • Parents • Faculty • Visitors
                </div>
              </div>
            </div>
          </div>

          <footer className="ciet-preview-footer">
            <p>© 2026 Chalapathi Institute of Engineering & Technology (CIET)</p>
            <p className="ciet-preview-footer-badge">Autonomous</p>
          </footer>
        </aside>

        <div className="ciet-preview-widget-area">
          {children}
        </div>
      </div>
    </div>
  );
}
