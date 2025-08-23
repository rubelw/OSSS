// src/osss-web/app/school-board/page.tsx
export const metadata = { title: "School Board • OSSS" };

export default function SchoolBoardPage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">School Board</h1>
        <p className="text-sm text-gray-600">
          Governance, meetings, agendas, minutes, and policy publications.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Meetings</h2>
          <p className="text-sm text-gray-600">Schedule, agendas, and minutes.</p>
        </div>
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Policies</h2>
          <p className="text-sm text-gray-600">Board policies and revisions.</p>
        </div>
      </div>
    </section>
  );
}
