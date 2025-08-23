// src/osss-web/app/transportation/page.tsx
export const metadata = { title: "Transportation • OSSS" };

export default function TransportationPage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Transportation</h1>
        <p className="text-sm text-gray-600">
          Routes, stops, and student assignments.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Routes & Stops</h2>
          <p className="text-sm text-gray-600">Plan and manage service (coming soon).</p>
        </div>
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Assignments</h2>
          <p className="text-sm text-gray-600">Student pickup/dropoff (coming soon).</p>
        </div>
      </div>
    </section>
  );
}
