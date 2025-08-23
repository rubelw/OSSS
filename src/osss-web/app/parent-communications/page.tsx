// src/osss-web/app/parent-communications/page.tsx
export const metadata = { title: "Parent Communications • OSSS" };

export default function ParentCommsPage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Parent Communications</h1>
        <p className="text-sm text-gray-600">
          Channels, posts, subscriptions, and deliveries.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Channels</h2>
          <p className="text-sm text-gray-600">Public, staff, and board (coming soon).</p>
        </div>
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Messages</h2>
          <p className="text-sm text-gray-600">Posts, attachments, delivery logs (coming soon).</p>
        </div>
      </div>
    </section>
  );
}
