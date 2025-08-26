// app/page.tsx (server component)
import { auth } from "@/app/api/auth/[...nextauth]/route";
import SessionDebugClaims from "@/components/SessionDebugClaims";

export default async function Page() {
  const session = await auth(); // OK in server component
  const loggedIn = !!session;

  return (
    <div className="space-y-6">
      {/* Existing minimal session dump */}
      {/* ... */}

      {/* New KC detail loader (does not bloat cookies) */}
      <h2 className="text-lg font-semibold">Keycloak Details</h2>
      <SessionDebugClaims />
    </div>
  );
}
