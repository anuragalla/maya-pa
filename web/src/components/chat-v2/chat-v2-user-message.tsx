import { MessagePrimitive, useMessage } from "@assistant-ui/react";

import { DocCard } from "@/components/documents/doc-card";
import type { MessageDocAttachment } from "@/lib/documents";

interface Props {
  phone: string;
}

export function ChatV2UserMessage({ phone }: Props) {
  const message = useMessage();
  const custom = message.metadata?.custom as
    | { documents?: MessageDocAttachment[] | null }
    | undefined;
  const documents = custom?.documents ?? [];

  return (
    <MessagePrimitive.Root className="group is-user flex w-full justify-end">
      <div className="flex w-fit max-w-[95%] flex-col gap-2 rounded-2xl rounded-br-md bg-primary px-4 py-3 text-sm text-primary-foreground">
        {documents.length > 0 && (
          <div className="flex flex-col gap-2">
            {documents.map((d) => (
              <DocCard
                key={d.document_id}
                documentId={d.document_id}
                phone={phone}
                filename={d.original_filename}
                docType={d.doc_type}
                status={d.status}
              />
            ))}
          </div>
        )}
        <MessagePrimitive.Parts />
      </div>
    </MessagePrimitive.Root>
  );
}
