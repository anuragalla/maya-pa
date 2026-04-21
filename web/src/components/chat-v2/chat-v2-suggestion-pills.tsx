import { useThreadRuntime } from "@assistant-ui/react";

interface Props {
  suggestions: string[];
}

export function ChatV2SuggestionPills({ suggestions }: Props) {
  const runtime = useThreadRuntime();
  if (suggestions.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {suggestions.map((s) => (
        <button
          key={s}
          type="button"
          onClick={() =>
            runtime.append({
              role: "user",
              content: [{ type: "text", text: s }],
            })
          }
          className="rounded-full border border-accent/25 bg-accent/10 px-3 py-1.5 text-xs font-medium text-accent transition-colors hover:bg-accent/15"
        >
          {s}
        </button>
      ))}
    </div>
  );
}
