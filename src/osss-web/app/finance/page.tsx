// src/osss-web/app/finance/page.tsx
export const metadata = { title: "Finance • OSSS" };

export default function FinancePage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Finance</h1>
        <p className="text-sm text-gray-600">
          GL, budgeting, payroll, and purchasing.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">General Ledger</h2>
          <p className="text-sm text-gray-600">Accounts & postings (coming soon).</p>
        </div>
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Payroll</h2>
          <p className="text-sm text-gray-600">Runs, checks, deductions (coming soon).</p>
        </div>
      </div>
    </section>
  );
}
