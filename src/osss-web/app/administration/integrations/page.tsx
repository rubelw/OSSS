// src/osss-web/app/administration/integrations/page.tsx
export const metadata = { title: "Integrations • Administration • OSSS" };

export default function IntegrationsPage() {
  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Integrations</h1>
      <p className="text-sm text-gray-600">
        Configure identity providers, SIS imports, and outbound webhooks.
      </p>

      <div className="rounded-lg border p-4">
        <p className="text-sm text-gray-700">Coming soon.</p>
      </div>
    </section>
  );
}
