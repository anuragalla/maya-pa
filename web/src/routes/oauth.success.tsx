import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { CheckCircleIcon } from "lucide-react";

export const Route = createFileRoute("/oauth/success")({
  component: OAuthSuccess,
});

function OAuthSuccess() {
  const navigate = useNavigate();
  const [countdown, setCountdown] = useState(3);

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) {
          clearInterval(timer);
          navigate({ to: "/" });
          return 0;
        }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [navigate]);

  return (
    <div className="flex h-dvh flex-col items-center justify-center gap-4 bg-background text-foreground">
      <CheckCircleIcon className="size-12 text-success" />
      <h1 className="text-xl font-semibold">Calendar Connected</h1>
      <p className="text-sm text-muted-foreground">
        Redirecting back to chat in {countdown}...
      </p>
      <button
        onClick={() => navigate({ to: "/" })}
        className="mt-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
      >
        Go to Chat
      </button>
    </div>
  );
}
