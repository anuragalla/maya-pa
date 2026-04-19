import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ChatView } from "@/components/chat-view";
import { Header } from "@/components/header";

const USERS = [
  { phone: "+19084329987", name: "Nigel" },
  { phone: "+19083612019", name: "Murthy" },
  { phone: "+12243347204", name: "Pragya" },
] as const;

export const Route = createFileRoute("/")({
  component: IndexPage,
});

function IndexPage() {
  const [phone, setPhone] = useState<string>(USERS[0].phone);
  const user = USERS.find((u) => u.phone === phone) ?? USERS[0];

  return (
    <>
      <Header users={USERS} selectedPhone={phone} onUserChange={setPhone} />
      <ChatView phone={phone} userName={user.name} key={phone} />
    </>
  );
}
