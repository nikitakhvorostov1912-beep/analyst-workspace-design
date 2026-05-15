"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import { highlightAnonTokens } from "@/lib/anon-tokens";

/**
 * Прогоняет children через highlightAnonTokens если children — строка.
 * Иначе возвращает children как есть (React-элемент не трогаем).
 */
function renderWithAnon(children: React.ReactNode): React.ReactNode {
  if (typeof children === "string") {
    return highlightAnonTokens(children);
  }
  return children;
}

/** Whitelist компонентов — без dangerouslySetInnerHTML и без rawHTML (XSS guard). */
const components: Components = {
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[var(--accent)] underline underline-offset-2 hover:opacity-80"
    >
      {children}
    </a>
  ),
  code: ({ className, children, ...props }) => {
    const isBlock = className?.includes("language-");
    if (isBlock) {
      return (
        <pre className="overflow-x-auto rounded-md bg-[var(--bg-elevated)] border border-[var(--border)] p-3 my-2">
          <code className={`text-xs font-mono text-[var(--fg)] ${className ?? ""}`} {...props}>
            {children}
          </code>
        </pre>
      );
    }
    return (
      <code
        className="bg-[var(--bg-elevated)] border border-[var(--border)] px-1 py-0.5 rounded text-xs font-mono"
        {...props}
      >
        {children}
      </code>
    );
  },
  table: ({ children }) => (
    <div className="overflow-x-auto my-2">
      <table className="w-full text-sm border-collapse border border-[var(--border)]">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-[var(--bg-elevated)]">{children}</thead>
  ),
  tbody: ({ children }) => <tbody>{children}</tbody>,
  tr: ({ children }) => (
    <tr className="border-b border-[var(--border)]">{children}</tr>
  ),
  th: ({ children }) => (
    <th className="px-3 py-1.5 text-left text-xs font-medium text-[var(--fg-muted)] border border-[var(--border)]">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-1.5 text-sm text-[var(--fg)] border border-[var(--border)]">
      {renderWithAnon(children)}
    </td>
  ),
  ul: ({ children }) => (
    <ul className="list-disc list-inside my-1 space-y-0.5 text-[var(--fg)]">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-inside my-1 space-y-0.5 text-[var(--fg)]">{children}</ol>
  ),
  li: ({ children }) => <li className="text-sm">{renderWithAnon(children)}</li>,
  h1: ({ children }) => (
    <h1 className="text-lg font-semibold text-[var(--fg)] mt-3 mb-1">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-base font-semibold text-[var(--fg)] mt-2 mb-1">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-sm font-semibold text-[var(--fg)] mt-2 mb-0.5">{children}</h3>
  ),
  p: ({ children }) => (
    <p className="text-sm text-[var(--fg)] leading-relaxed mb-1">{renderWithAnon(children)}</p>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-[var(--border)] pl-3 my-1 text-[var(--fg-muted)] italic">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="border-[var(--border)] my-2" />,
  strong: ({ children }) => (
    <strong className="font-semibold text-[var(--fg)]">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic text-[var(--fg)]">{children}</em>
  ),
};

interface MarkdownProps {
  children: string;
}

/** Безопасный markdown рендерер — без rehype-raw, без dangerouslySetInnerHTML. */
export function Markdown({ children }: MarkdownProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={components}
      // Запрет на HTML в markdown-источнике (T-01-11 XSS guard)
      disallowedElements={["script", "iframe", "object", "embed", "style"]}
      unwrapDisallowed
    >
      {children}
    </ReactMarkdown>
  );
}
