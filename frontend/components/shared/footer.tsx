import Link from "next/link";

export function Footer() {
  return (
    <footer className="relative z-[2] mt-32 border-t border-[var(--color-ink-line)]">
      <div className="mx-auto max-w-[1280px] px-8 py-14">
        <div className="grid grid-cols-1 md:grid-cols-[1.5fr_1fr_1fr_1fr] gap-10">
          <div className="space-y-4">
            <p className="font-display text-3xl leading-tight text-[var(--color-ink)] text-balance">
              <span className="ink-underline">RAG</span> with cited answers.
            </p>
            <p className="text-sm text-[var(--color-ink-soft)] max-w-md leading-relaxed">
              An open reference build. Hybrid retrieval, refuse-on-bad-citation,
              50-question eval set running in CI.
            </p>
          </div>

          <FooterCol title="Project">
            <FooterLink href="/eval">Eval scorecard</FooterLink>
            <FooterLink href="https://github.com/AmirD10224/docs-rag" ext>
              Source code
            </FooterLink>
            <FooterLink
              href="https://github.com/AmirD10224/docs-rag/blob/main/ARCHITECTURE.md"
              ext
            >
              Architecture
            </FooterLink>
          </FooterCol>

          <FooterCol title="Made by">
            <FooterLink href="https://github.com/AmirD10224" ext>
              Amir Dhibi
            </FooterLink>
            <FooterLink href="mailto:amir10.dhibi@gmail.com">Email</FooterLink>
          </FooterCol>

          <FooterCol title="Legal">
            <FooterLink
              href="https://github.com/AmirD10224/docs-rag/blob/main/LICENSE"
              ext
            >
              MIT License
            </FooterLink>
          </FooterCol>
        </div>

        <div className="mt-12 pt-6 border-t border-[var(--color-ink-line-soft)] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <p className="font-mono text-[11px] text-[var(--color-ink-faint)] tracking-wider uppercase">
            docs-rag · v0.1.0 · 2026
          </p>
          <p className="font-mono text-[11px] text-[var(--color-ink-faint)]">
            MIT · no analytics
          </p>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <p className="label-caps">{title}</p>
      <ul className="space-y-2">{children}</ul>
    </div>
  );
}

function FooterLink({
  href,
  children,
  ext,
}: {
  href: string;
  children: React.ReactNode;
  ext?: boolean;
}) {
  const Tag: React.ElementType = ext ? "a" : Link;
  return (
    <li>
      <Tag
        {...(ext ? { href, target: "_blank", rel: "noreferrer" } : { href })}
        className="text-sm text-[var(--color-ink-soft)] hover:text-[var(--color-accent)] transition-colors"
      >
        {children}
      </Tag>
    </li>
  );
}
