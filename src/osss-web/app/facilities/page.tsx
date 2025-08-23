// src/osss-web/app/facilities/page.tsx
export const metadata = { title: "Facilities • OSSS" };

export default function FacilitiesPage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Facilities</h1>
        <p className="text-sm text-gray-600">
          Buildings, spaces, maintenance, and work orders.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Work Orders</h2>
          <p className="text-sm text-gray-600">Track and manage requests (coming soon).</p>
        </div>
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Assets</h2>
          <p className="text-sm text-gray-600">Inventory and warranties (coming soon).</p>
        </div>
      </div>
    </section>
  );
}
