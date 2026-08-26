/**
 * The registration rules, checked before the request is sent.
 *
 * The server is the authority — every one of these is enforced again in
 * `app/schemas/auth.py`, and a client check is a courtesy, never a control.
 * The courtesy is worth having: a password rejected after a round trip is
 * rejected *along with* the rest of the form, and the student re-reads five
 * fields to find out which one was wrong.
 *
 * Each rule mirrors a specific server-side one, and the comment names it, so a
 * change on one side is visibly a change on the other.
 */

/** bcrypt ignores everything past 72 bytes, so the server caps the password there. */
export const PASSWORD_MIN = 8;
export const PASSWORD_MAX_BYTES = 72;

export const NAME_MIN = 2;
export const NAME_MAX = 200;
export const CLASS_CODE_MAX = 32;

export interface FieldErrors {
  [field: string]: string | undefined;
}

export interface RegistrationInput {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
  gender: string | null;
  classCode: string;
}

/**
 * How many bytes a password occupies, not how many characters it has.
 *
 * The server's limit is a byte limit because bcrypt's is. An accented or
 * non-Latin character costs two or three, so counting characters here would
 * accept a password the server then rejects — for the students least likely to
 * guess why.
 */
export function passwordByteLength(password: string): number {
  return new TextEncoder().encode(password).length;
}

/** The requirements, each with whether this password meets it. */
export function passwordChecklist(password: string) {
  return [
    { label: `At least ${PASSWORD_MIN} characters`, met: password.length >= PASSWORD_MIN },
    { label: "A letter", met: /[A-Za-z]/.test(password) },
    { label: "A number", met: /\d/.test(password) },
  ];
}

export function validateRegistration(input: RegistrationInput): FieldErrors {
  const errors: FieldErrors = {};
  const name = input.fullName.trim();

  if (name.length < NAME_MIN) {
    errors.full_name = `Please enter your full name — at least ${NAME_MIN} characters.`;
  } else if (name.length > NAME_MAX) {
    errors.full_name = `That name is longer than ${NAME_MAX} characters.`;
  }

  // Deliberately not a strict address grammar. The only address that matters
  // is one that receives mail, which no regular expression can tell you; this
  // catches the typo where the @ or the domain is missing and leaves the rest
  // to the server.
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.email.trim())) {
    errors.email = "Please enter an email address like you@university.edu.";
  }

  if (input.password.length < PASSWORD_MIN) {
    errors.password = `Passwords need at least ${PASSWORD_MIN} characters.`;
  } else if (passwordByteLength(input.password) > PASSWORD_MAX_BYTES) {
    errors.password =
      "That password is too long. Accented and non-Latin characters count more than once.";
  } else if (!/[A-Za-z]/.test(input.password) || !/\d/.test(input.password)) {
    errors.password = "Include at least one letter and one number.";
  }

  if (input.confirmPassword !== input.password) {
    // Client-side only: the server never sees this field. It exists because a
    // mistyped password on a new account cannot be recovered by trying again —
    // there is nothing to compare against.
    errors.confirm_password = "These two passwords do not match.";
  }

  if (input.gender !== "male" && input.gender !== "female") {
    errors.gender = "Choose the avatar set your rewards will use.";
  }

  if (input.classCode.trim().length > CLASS_CODE_MAX) {
    errors.class_code = `A class code is at most ${CLASS_CODE_MAX} characters.`;
  }

  return errors;
}

export function hasErrors(errors: FieldErrors): boolean {
  return Object.values(errors).some(Boolean);
}
