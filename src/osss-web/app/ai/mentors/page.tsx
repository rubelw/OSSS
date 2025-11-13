// src/osss-web/app/ai/mentors/page.tsx
import MentorClient from "./MentorClient";

export const metadata = { title: "Mentors • AI • OSSS" };

export default function MentorsPage() {
  return (
    <section className="space-y-4 w-full max-w-screen-xl mx-auto">
      {/* ... */}
      <MentorClient />
    </section>
  );
}