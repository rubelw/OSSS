// src/osss-web/app/administration/page.tsx
import Link from "next/link";

export const metadata = { title: "Administration • OSSS" };

const cards = [
  { href: "/administration/a2a", title: "A2A-Server", blurb: "A2A Server" },
  { href: "/administration/organizations", title: "Organizations", blurb: "Districts, schools, calendars." },
  { href: "/administration/users-roles", title: "Users & Roles", blurb: "Accounts, roles, permissions." },
  { href: "/administration/integrations", title: "Integrations", blurb: "Identity providers, imports, webhooks." },
  { href: "/administration/system-settings", title: "System Settings", blurb: "Feature flags, environments, health." },
];

export default function AdministrationPage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Administration</h1>
        <p className="text-sm text-gray-600">
          District & site configuration, users, roles, permissions, and system settings.
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
            <p className="text-sm text-gray-600">{c.blurb}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
