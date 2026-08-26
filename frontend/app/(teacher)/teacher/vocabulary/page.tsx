"use client";

import { Protected } from "@/components/auth/protected";
import { VocabularyManager } from "@/components/vocabulary/vocabulary-manager";

export default function TeacherVocabularyPage() {
  return (
    <Protected roles={["teacher", "admin"]}>
      <VocabularyManager />
    </Protected>
  );
}
