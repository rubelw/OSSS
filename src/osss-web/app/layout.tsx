// src/osss-web/app/layout.tsx
import type { Metadata } from "next";
import Link from "next/link";
import Providers from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "OSSS Web",
  description: "Open Source School Software",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-gray-900">
        <Providers>
          <header className="border-b bg-gray-50">
            <nav className="mx-auto max-w-6xl px-4 py-3 flex items-center gap-4">
              <Link href="/" className="font-semibold">
                OSSS Web
              </Link>
              <div className="flex items-center gap-3 text-sm">
                <Link href="/states" className="hover:underline">
                  States
                </Link>
                <Link href="/schools" className="hover:underline">
                  Schools
                </Link>
              </div>
            </nav>
          </header>

          <main className="mx-auto max-w-6xl px-4 py-6">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
