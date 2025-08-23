// src/osss-web/app/layout.tsx
import type { Metadata } from "next";
import Providers from "./providers";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "OSSS Web",
  description: "Open Source School Software",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="w-full border-b bg-white">
          <nav className="mx-auto flex max-w-5xl items-center gap-4 p-4">
            <Link href="/" className="font-semibold">OSSS</Link>
            <div className="ml-auto flex items-center gap-4">
              {/* New: singular “School” links to the main page */}
              <Link href="/" className="hover:underline">
                School
              </Link>
              {/* Existing links */}
              <Link href="/states" className="hover:underline">
                States
              </Link>
              <Link href="/schools" className="hover:underline">
                Schools
              </Link>
            </div>
          </nav>
        </header>

        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
