import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { RegisterFlow } from "@/components/auth/register-flow";

export const metadata: Metadata = {
  title: "Create an account",
  description: "Create a GraphMaster account and start practising graph description in English.",
};

export default function RegisterPage() {
  return (
    <AuthShell>
      <RegisterFlow />
    </AuthShell>
  );
}
