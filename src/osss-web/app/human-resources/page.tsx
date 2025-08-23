// src/osss-web/app/human-resources/page.tsx
export const metadata = { title: "Human Resources • OSSS" };

export default function HumanResourcesPage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Human Resources</h1>
        <p className="text-sm text-gray-600">
          Employees, positions, assignments, and payroll alignment.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Employees</h2>
          <p className="text-sm text-gray-600">
            Profiles, status, and employment details (coming soon).
          </p>
        </div>

        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Positions</h2>
          <p className="text-sm text-gray-600">
            Titles, departments, and FTE (coming soon).
          </p>
        </div>

        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Assignments</h2>
          <p className="text-sm text-gray-600">
            Position assignments and funding splits (coming soon).
          </p>
        </div>

        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Payroll Bridge</h2>
          <p className="text-sm text-gray-600">
            Pay periods, runs, earnings & deductions (coming soon).
          </p>
        </div>
      </div>
    </section>
  );
}
