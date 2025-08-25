// src/osss-web/app/sis/page.tsx
import Link from "next/link";

export const metadata = { title: "Student Information System • OSSS" };

export default function SISPage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Student Information System</h1>
        <p className="text-sm text-gray-600">
          Core student records, enrollments, attendance, grading, and reporting.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <Link href="/api/schools" className="rounded-lg border p-4 hover:bg-gray-50">
          <h2 className="font-medium">Schools</h2>
          <p className="text-sm text-gray-600">Browse schools from the SIS.</p>
        </Link>

        <Link
          href="/api/behaviorcodes"
          className="rounded-lg border p-4 hover:bg-gray-50"
        >
          <h2 className="font-medium">Behavior Codes</h2>
          <p className="text-sm text-gray-600">District-wide behavior codes.</p>
        </Link>

        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Students</h2>
          <p className="text-sm text-gray-600">Profiles and enrollments (coming soon).</p>
        </div>
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Attendance</h2>
          <p className="text-sm text-gray-600">Daily and period attendance (coming soon).</p>
        </div>
      </div>
    </section>
  );
}
