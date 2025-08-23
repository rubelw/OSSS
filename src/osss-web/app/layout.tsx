// src/osss-web/app/layout.tsx
import type { Metadata } from "next";
import Link from "next/link";
import Providers from "./providers";
import "./globals.css";

// Auth.js v5 (NextAuth v5) helpers you exported from "@/lib/auth"
import { auth, signIn, signOut } from "@/lib/auth";

export const metadata: Metadata = {
  title: "OSSS Web",
  description: "Open Source School Software",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();

  return (
    <html lang="en">
      <body>
        <Providers>
          {/* Top Bar */}
          <header className="header-glass sticky top-0 z-40">
            <div className="container-max flex items-center justify-between px-4 md:px-6 py-3">
              <div className="flex items-center gap-3">
                <Link href="/" className="inline-flex items-center gap-2">
                  <span className="inline-block h-2.5 w-2.5 rounded-full bg-blue-500"></span>
                  <span className="font-semibold tracking-tight">OSSS</span>
                </Link>
                <nav className="hidden md:flex items-center gap-3 ml-6 text-sm">
                  <Link className="link-nav" href="/school-board">School Board</Link>
                  <Link className="link-nav" href="/sis">Student Information System</Link>
                  <Link className="link-nav" href="/facilities">Facilities</Link>
                  <Link className="link-nav" href="/transportation">Transportation</Link>
                  <Link className="link-nav" href="/finance">Finance</Link>
                  <Link className="link-nav" href="/communications">Parent Communications</Link>
                  <Link className="link-nav" href="/human-resources">Human Resources</Link>
                  <Link className="link-nav" href="/administration">Administration</Link>
                </nav>
              </div>

              {/* Auth actions */}
              <div className="flex items-center gap-2">
                {session ? (
                  <form>
                    {/* server action (Auth.js v5) */}
                    <button
                      className="btn"
                      formAction={async () => {
                        "use server";
                        await signOut();
                      }}
                    >
                      Sign out
                    </button>
                  </form>
                ) : (
                  <form>
                    <button
                      className="btn btn-primary"
                      formAction={async () => {
                        "use server";
                        await signIn("keycloak");
                      }}
                    >
                      Sign in
                    </button>
                  </form>
                )}
              </div>
            </div>
          </header>

          {/* App Shell */}
          <div className="grid grid-cols-1 md:grid-cols-[16rem_1fr] min-h-[calc(100vh-3.25rem)]">
            {/* Sidebar */}
            <aside className="sidebar-surface" style={{ width: 260 }}>
              <div className="p-4">
                <div className="section-label">Quick Links</div>
                <nav className="sidebar-section">
                  <Link href="/" className="link-nav">Home</Link>
                  <Link href="/schools" className="link-nav">Schools</Link>
                  <Link href="/behavior-codes" className="link-nav">Behavior Codes</Link>
                </nav>

                <div className="section-label">Modules</div>
                <nav className="sidebar-section">
                  <Link href="/student-information-system" className="link-nav">Student Information System</Link>
                  <Link href="/facilities" className="link-nav">Facilities</Link>
                  <Link href="/transportation" className="link-nav">Transportation</Link>
                  <Link href="/finance" className="link-nav">Finance</Link>
                  <Link href="/parent-communications" className="link-nav">Parent Communications</Link>
                  <Link href="/human-resources" className="link-nav">Human Resources</Link>
                  <Link href="/administration" className="link-nav">Administration</Link>
                </nav>
              </div>
            </aside>

            {/* Main Content */}
            <main className="main-surface">
              <div className="container-max px-4 md:px-6 py-6">{children}</div>
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
