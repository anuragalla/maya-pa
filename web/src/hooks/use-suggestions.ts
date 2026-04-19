interface SuggestionsDataItem {
  type: "suggestions";
  items: string[];
}

function isSuggestionsItem(item: unknown): item is SuggestionsDataItem {
  return (
    typeof item === "object" &&
    item !== null &&
    (item as SuggestionsDataItem).type === "suggestions" &&
    Array.isArray((item as SuggestionsDataItem).items)
  );
}

export function useSuggestions(data: unknown[] | undefined): string[] {
  if (!data?.length) return [];
  for (let i = data.length - 1; i >= 0; i--) {
    const item = data[i];
    if (isSuggestionsItem(item)) return item.items;
  }
  return [];
}
