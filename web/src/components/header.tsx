import { MoonIcon, SunIcon } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import { useTheme } from "@/hooks/use-theme";

interface User {
  readonly phone: string;
  readonly name: string;
}

interface HeaderProps {
  users: readonly User[];
  selectedPhone: string;
  onUserChange: (phone: string) => void;
}

export function Header({ users, selectedPhone, onUserChange }: HeaderProps) {
  const selectedUser = users.find((u) => u.phone === selectedPhone);
  const { theme, toggle } = useTheme();

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-5">
      <div className="flex items-center gap-2.5">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
          L
        </div>
        <span className="font-heading text-sm font-semibold text-foreground">
          Live150
        </span>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={toggle}
          className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-card hover:text-foreground"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? (
            <SunIcon className="size-4" />
          ) : (
            <MoonIcon className="size-4" />
          )}
        </button>
        <Select
          value={selectedPhone}
          onValueChange={(val) => val && onUserChange(val)}
        >
          <SelectTrigger
            size="sm"
            className="w-auto gap-2 border-none bg-transparent text-xs text-muted-foreground shadow-none hover:text-foreground"
            aria-label="Select user"
          >
            <span>{selectedUser?.name ?? "Select user"}</span>
          </SelectTrigger>
          <SelectContent className="rounded-lg border-border bg-card">
            {users.map((u) => (
              <SelectItem key={u.phone} value={u.phone}>
                {u.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </header>
  );
}
