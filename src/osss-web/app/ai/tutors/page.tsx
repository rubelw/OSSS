// src/osss-web/app/ai/tutors/page.tsx
import TutorClient from "./TutorClient";

export const metadata = { title: "Tutors • AI • OSSS" };

export default function TutorsPage() {
  return (
    <section className="space-y-4 w-full max-w-screen-xl mx-auto">
      {/* ... */}
      <TutorClient />
    </section>
  );
}
