import ChatClient from "./ChatClient";

export const metadata = { title: "Chat • AI • OSSS" };

export default function ChatPage() {
  return (
    <section className="w-full h-screen">
      <ChatClient />
    </section>
  );
}

