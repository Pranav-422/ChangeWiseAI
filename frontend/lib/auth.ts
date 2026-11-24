/** Only a path inside this application may follow a sign-in. */
export function safePath(next: string | null | undefined, fallback = "/dashboard") {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.includes("\\") ? next : fallback;
}

const MESSAGES: Record<string, string> = {
  invalid_credentials: "The email or password is not correct.",
  email_not_confirmed: "Confirm your email address first. The link is in your inbox.",
  user_already_exists: "An account with this email already exists.",
  weak_password: "Choose a longer password, at least 8 characters.",
  over_email_send_rate_limit: "Too many emails were requested. Wait a few minutes.",
  same_password: "Choose a password you have not used before.",
};
export const authMessage = (error: { code?: string; message: string }) => MESSAGES[error.code ?? ""] ?? error.message;
