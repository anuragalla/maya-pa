import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import { ChatV2View } from "@/components/chat-v2/chat-v2-view";
import { Header } from "@/components/header";

const USERS = [
  { phone: "+19084329987", name: "Nigel" },
  { phone: "+19083612019", name: "Murthy" },
  { phone: "+12243347204", name: "Pragya" },
] as const;

export const Route = createFileRoute("/chatv2")({
  component: ChatV2Page,
});

function ChatV2Page() {
  const [phone, setPhone] = useState<string>(USERS[0].phone);
  const user = USERS.find((u) => u.phone === phone) ?? USERS[0];

  return (
    <>
      <Header users={USERS} selectedPhone={phone} onUserChange={setPhone} />
      <ChatV2View phone={phone} userName={user.name} key={phone} />
    </>
  );
}
