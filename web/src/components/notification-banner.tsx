import { Bell, X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface NotificationBannerProps {
  title: string;
  body: string;
  onDismiss: () => void;
}

export function NotificationBanner({ title, body, onDismiss }: NotificationBannerProps) {
  return (
    <div className="mx-auto flex max-w-[640px] items-start gap-3 rounded-2xl border border-notification/20 bg-notification/5 px-4 py-3">
      <Bell className="mt-0.5 size-4 shrink-0 text-notification" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-sm text-muted-foreground">{body}</p>
      </div>
      <Button
        variant="ghost"
        size="icon-xs"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="cursor-pointer text-muted-foreground hover:text-foreground"
      >
        <X className="size-3.5" />
      </Button>
    </div>
  );
}
