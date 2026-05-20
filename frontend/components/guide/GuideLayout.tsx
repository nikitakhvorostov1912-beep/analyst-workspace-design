"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export interface GuideSection {
  /** Якорь раздела — попадает в URL hash и в id заголовка. */
  id: string;
  /** Видимое название в TOC и в заголовке секции. */
  title: string;
  /** Короткая подпись под title в TOC (опционально). */
  hint?: string;
  /** Содержимое секции. */
  content: React.ReactNode;
}

interface GuideLayoutProps {
  sections: GuideSection[];
  /** Заголовок документа сверху. */
  title?: string;
  /** Подзаголовок под заголовком. */
  subtitle?: string;
}

/**
 * Layout полноценного in-app гайда с sticky TOC слева и контентом справа.
 *
 * Что делает:
 *   - Рендерит заголовок, ссылку «На главную», подзаголовок.
 *   - Слева — sticky TOC со списком секций, активная подсвечивается.
 *   - Справа — секции с anchor-id, между ними тонкие разделители.
 *   - Scroll-spy: при прокрутке обновляет активную секцию через IntersectionObserver.
 *   - При клике в TOC — smooth scroll к секции + обновление hash.
 *
 * Дизайн соответствует brand Stencil: IBM Plex Sans + JetBrains Mono для якорей.
 */
export function GuideLayout({ sections, title, subtitle }: GuideLayoutProps) {
  const [activeId, setActiveId] = useState<string>(sections[0]?.id ?? "");

  useEffect(() => {
    if (sections.length === 0) return undefined;
    // IntersectionObserver: первая видимая секция = активная
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
            break;
          }
        }
      },
      {
        rootMargin: "-80px 0px -60% 0px",
        threshold: [0, 0.5, 1],
      },
    );

    for (const section of sections) {
      const el = document.getElementById(section.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [sections]);

  // По загрузке — если в URL есть hash, скроллим
  useEffect(() => {
    if (typeof window === "undefined") return;
    const hash = window.location.hash.slice(1);
    if (!hash) return;
    const el = document.getElementById(hash);
    if (el) {
      // даём layout сесть
      setTimeout(() => el.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    }
  }, []);

  function handleTocClick(e: React.MouseEvent<HTMLAnchorElement>, id: string) {
    e.preventDefault();
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      window.history.replaceState(null, "", `#${id}`);
      setActiveId(id);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--fg-1)]">
      {/* Top bar — назад + заголовок */}
      <div className="sticky top-0 z-20 border-b border-[var(--bd-1)] bg-[var(--bg)]/95 backdrop-blur supports-[backdrop-filter]:bg-[var(--bg)]/80">
        <div className="max-w-[1180px] mx-auto px-6 h-12 flex items-center gap-4">
          <Link
            href="/"
            className="text-[var(--fg-3)] hover:text-[var(--fg-1)] transition-colors flex items-center gap-1.5 text-sm"
          >
            <ArrowLeft size={15} />
            На главную
          </Link>
          {title && (
            <h1
              className="text-[15px] font-semibold tracking-tight text-[var(--fg-1)]"
              style={{ fontFamily: "var(--font-plex-sans), system-ui" }}
            >
              {title}
            </h1>
          )}
        </div>
      </div>

      {/* Шапка */}
      {(title || subtitle) && (
        <div className="max-w-[1180px] mx-auto px-6 pt-10 pb-6">
          {title && (
            <h2
              className="text-[32px] font-semibold leading-tight tracking-tight text-[var(--fg-1)]"
              style={{ fontFamily: "var(--font-plex-sans), system-ui" }}
            >
              {title}
            </h2>
          )}
          {subtitle && (
            <p className="mt-3 text-[15px] text-[var(--fg-2)] leading-relaxed max-w-[760px]">
              {subtitle}
            </p>
          )}
        </div>
      )}

      {/* Контент: TOC + секции */}
      <div className="max-w-[1180px] mx-auto px-6 pb-24 grid grid-cols-[240px_1fr] gap-10">
        {/* Left TOC */}
        <nav
          className="sticky top-[60px] self-start max-h-[calc(100vh-80px)] overflow-y-auto pr-2"
          aria-label="Содержание"
        >
          <div
            className="text-[10px] font-medium uppercase tracking-[0.18em] text-[var(--fg-3)] mb-3"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            Содержание
          </div>
          <ol className="space-y-0.5">
            {sections.map((section, idx) => {
              const isActive = section.id === activeId;
              return (
                <li key={section.id}>
                  <a
                    href={`#${section.id}`}
                    onClick={(e) => handleTocClick(e, section.id)}
                    className={`block px-2.5 py-1.5 rounded text-[13px] leading-snug transition-colors ${
                      isActive
                        ? "bg-[var(--accent-12)] text-[var(--fg-1)] font-medium"
                        : "text-[var(--fg-2)] hover:bg-[var(--bg-2)] hover:text-[var(--fg-1)]"
                    }`}
                  >
                    <span
                      className="inline-block w-6 text-[var(--fg-3)] tabular-nums"
                      style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
                    >
                      {String(idx + 1).padStart(2, "0")}
                    </span>
                    {section.title}
                  </a>
                </li>
              );
            })}
          </ol>
        </nav>

        {/* Right content */}
        <article className="min-w-0 max-w-[760px]">
          {sections.map((section, idx) => (
            <section
              key={section.id}
              id={section.id}
              className="scroll-mt-20 mb-16 last:mb-0"
            >
              <header className="mb-5 pb-3 border-b border-[var(--bd-1)] flex items-baseline gap-3">
                <span
                  className="text-[12px] text-[var(--fg-3)] tabular-nums"
                  style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
                >
                  {String(idx + 1).padStart(2, "0")}
                </span>
                <h2
                  className="text-[22px] font-semibold tracking-tight text-[var(--fg-1)]"
                  style={{ fontFamily: "var(--font-plex-sans), system-ui" }}
                >
                  {section.title}
                </h2>
              </header>
              <div className="prose-guide">{section.content}</div>
            </section>
          ))}
        </article>
      </div>
    </div>
  );
}
