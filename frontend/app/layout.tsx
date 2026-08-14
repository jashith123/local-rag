import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { NavLink } from "@/components/NavLink";
import { ThemeToggle } from "@/components/ThemeToggle";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Enterprise AI Platform",
  description: "Upload documents and search them by meaning",
};

// Runs before first paint so the page never flashes light then snaps to dark.
// It has to be inline for that: any external script arrives too late.
const THEME_BOOT = `
try {
  var stored = localStorage.getItem("theme");
  var dark = stored
    ? stored === "dark"
    : window.matchMedia("(prefers-color-scheme: dark)").matches;
  if (dark) document.documentElement.classList.add("dark");
} catch (e) {}
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // suppressHydrationWarning: the boot script above adds a class the server
    // markup can't know about, and that mismatch is expected here.
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
      </head>
      <body className="flex min-h-full flex-col bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
        <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/80 backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-950/80">
          <div className="mx-auto flex h-14 max-w-5xl items-center gap-6 px-6">
            <span className="flex items-center gap-2 font-semibold tracking-tight">
              <span
                className="grid h-6 w-6 place-items-center rounded-md bg-zinc-900 text-[11px] font-bold text-white dark:bg-zinc-100 dark:text-zinc-900"
                aria-hidden
              >
                AI
              </span>
              <span className="hidden sm:inline">Enterprise AI Platform</span>
            </span>

            <nav className="flex gap-1 text-sm">
              <NavLink href="/">Documents</NavLink>
              <NavLink href="/search">Search</NavLink>
              <NavLink href="/chat">Chat</NavLink>
            </nav>

            <div className="ml-auto flex items-center gap-1">
              <a
                href="http://127.0.0.1:8000/docs"
                target="_blank"
                rel="noreferrer"
                className="rounded-lg px-2 py-1.5 text-xs text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
              >
                API docs ↗
              </a>
              <ThemeToggle />
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-8">
          {children}
        </main>

        <footer className="border-t border-zinc-200 py-4 dark:border-zinc-800">
          <p className="mx-auto max-w-5xl px-6 text-xs text-zinc-500">
            FastAPI · pypdf · all-MiniLM-L6-v2 · Qdrant
          </p>
        </footer>
      </body>
    </html>
  );
}
