// Simple client-side logout helper: wipes tokens and user info, then redirects to login
export function performLogout(redirectTo: string = "/") {
  try {
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("username");
      // Optionally nuke other app-specific caches here
    }
  } catch {}
  if (typeof window !== "undefined") {
    window.location.href = redirectTo;
  }
}
