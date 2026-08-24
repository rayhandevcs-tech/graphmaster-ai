import { ComingSoon } from "@/components/layout/coming-soon";

export const metadata = { title: "Create an account" };

export default function RegisterPage() {
  return (
    <ComingSoon
      title="Create an account"
      sprint="Sprint 11"
      backHref="/login"
      backLabel="Sign in instead"
    >
      Registration asks for a name, an email, a password and a gender — the last of these chooses
      the cartoon avatar that receives your rewards — plus an optional class code. The endpoint is
      live; the screen is next.
    </ComingSoon>
  );
}
