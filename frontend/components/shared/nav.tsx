"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

export function Nav() {
  return (
    <header className="sticky top-0 z-40 border-b border-[var(--color-ink-line)] bg-[var(--color-paper)]/85 backdrop-blur-xl backdrop-saturate-150">
      <div className="mx-auto max-w-[1280px] px-8 h-16 flex items-center justify-between">
        <Link
          href="/"
          className="group flex items-center gap-2.5 -ml-1 px-1 py-1 rounded-md hover:bg-[var(--color-paper-deep)] transition-colors"
        >
          <Image
            src="/logo.png"
            alt="docs-rag"
            width={32}
            height={32}
            priority
            className="h-7 w-7 object-contain"
          />
          <span className="font-display text-2xl text-[var(--color-ink)] leading-none tracking-tight">
            DocsRAG
          </span>
          <span className="font-mono text-[10.5px] text-[var(--color-ink-faint)] tracking-wider uppercase">
            v0.1.0
          </span>
        </Link>

        <nav className="flex items-center gap-1">
          <NavLink href="/eval">Eval</NavLink>
          <NavLink href="https://github.com/AmirD10224/docs-rag" external>
            Code
          </NavLink>
          <NavLink
            href="https://github.com/AmirD10224/docs-rag/blob/main/ARCHITECTURE.md"
            external
          >
            Architecture
          </NavLink>
          <a
            href="#try"
            className="ml-3 inline-flex items-center gap-1.5 rounded-full bg-[var(--color-ink)] text-[var(--color-paper-soft)] hover:bg-[var(--color-accent-deep)] transition-colors px-4 py-2 text-sm font-medium"
          >
            Try the demo
            <ArrowUpRight className="size-3.5" />
          </a>
        </nav>
      </div>
    </header>
  );
}

function NavLink({
  href,
  children,
  external,
}: {
  href: string;
  children: React.ReactNode;
  external?: boolean;
}) {
  const isExt = external || href.startsWith("http");
  const Tag: React.ElementType = isExt ? "a" : Link;
  return (
    <Tag
      {...(isExt ? { href, target: "_blank", rel: "noreferrer" } : { href })}
      className="px-3 py-2 text-sm text-[var(--color-ink-soft)] hover:text-[var(--color-ink)] transition-colors rounded-md"
    >
      {children}
    </Tag>
  );
}
