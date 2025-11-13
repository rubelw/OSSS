// src/osss-web/app/ai/page.tsx
import Link from "next/link";

export const metadata = { title: "ai • OSSS" };

const cards = [
  { href: "/ai/chat", title: "Chat", blurb: "Chat with AI directly." },
  { href: "/ai/mentors", title: "Mentors", blurb: "AI Mentors." },
  { href: "/ai/tutors", title: "Tutors", blurb: "AI Tutors." },
];

export default function AIPage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">AI</h1>
        <p className="text-sm text-gray-600">
          District AI Tools.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        {cards.map((c) => (
          <Link
            key={c.href}
            href={c.href}
            className="rounded-lg border p-4 hover:bg-gray-50 transition"
          >
            <h2 className="font-medium">{c.title}</h2>
          </Link>
        ))}
      </div>
    </section>
  );
}
