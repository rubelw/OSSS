
import ChatClient from "./ChatClient";

export const metadata = { title: "Chat • AI • OSSS" };

export default function ChatPage() {
  return (
    <section className="space-y-4 w-full max-w-screen-xl mx-auto">
      {/* ... */}
      <ChatClient />
    </section>
  );
}

