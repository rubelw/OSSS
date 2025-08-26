import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import Providers from "./providers";
import "./globals.css";
import { SignOutButton } from '@/components/SignOutButton';
import { SignInButton } from '@/components/SignInButton';


export const metadata: Metadata = {
  title: "OSSS Web",
  description: "Open Source School Software",
  icons: {
    icon: "/osss-logo.svg",          // favicon/tab icon
    shortcut: "/osss-logo.svg",
    apple: "/osss-logo.svg",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="app-shell">
            {/* Full-bleed header */}
            <header className="topbar">
              <div className="container topbar-inner">
                <Link href="/" className="brand" aria-label="OSSS Home">
                <Image
                    src="/logo.png"
                    alt="OSSS logo"
                    width={28}
                    height={28}
                    priority
                    className="brand-logo"
                  />
                  <span className="brand-text">OSSS</span>
                </Link>

                <nav className="topnav" aria-label="Primary">
                  <Link href="/events">Activities/Events</Link>
                </nav>

                <div className="actions">
                  {/* Swap to real auth buttons if desired */}
                  <SignInButton />
                  <SignOutButton />
                </div>
              </div>
            </header>

            {/* Sidebar + main content */}
            <div className="app-content">
              <aside className="sidebar">
                <section>
                  <h4>Quick Links</h4>
                  <Link href="/">Home</Link>
                  <Link href="/events">Activities/Events</Link>
                </section>

                <section>
                  <h4>Modules</h4>
                  <Link href="/activities">Activities</Link>
                  <Link href="/school-board">School Board</Link>
                  <Link href="/sis">Student Information System</Link>
                  <Link href="/facilities">Facilities</Link>
                  <Link href="/transportation">Transportation</Link>
                  <Link href="/finance">Finance</Link>
                  <Link href="/parent-communications">Parent Communications</Link>
                  <Link href="/human-resources">Human Resources</Link>
                  <Link href="/administration">Administration</Link>
                </section>
              </aside>

              <main className="main">{children}</main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
