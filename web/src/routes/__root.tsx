import { createRootRoute, Outlet, useNavigate, useLocation } from "@tanstack/react-router";
import { useEffect } from "react";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/hooks/use-theme";

export const Route = createRootRoute({
  component: RootLayout,
});

function RootLayout() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (location.pathname === "/login") return;
    if (!localStorage.getItem("maya_authed")) {
      navigate({ to: "/login" });
    }
  }, [location.pathname, navigate]);

  return (
    <ThemeProvider>
      <TooltipProvider>
        <Outlet />
        <Toaster position="top-center" />
      </TooltipProvider>
    </ThemeProvider>
  );
}
