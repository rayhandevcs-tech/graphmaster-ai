/**
 * Creating an account.
 *
 * Client-side validation is a courtesy, never a control — the server checks
 * every one of these again. The courtesy is what these cover: a form that
 * reports all of its problems at once rather than one per round trip, and one
 * that agrees with the server about what the rules are. A client rule that is
 * *stricter* than the server's is the dangerous kind: it rejects an account
 * the platform would have accepted, and the student has no way to find that
 * out.
 */

import * as React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { GenderChoice } from "@/components/auth/gender-choice";
import { PasswordField } from "@/components/auth/password-field";
import {
  passwordByteLength,
  validateRegistration,
  type RegistrationInput,
} from "@/lib/auth/validation";

function input(overrides: Partial<RegistrationInput> = {}): RegistrationInput {
  return {
    fullName: "Amina Yusuf",
    email: "amina@university.edu",
    password: "describe99",
    confirmPassword: "describe99",
    gender: "female",
    classCode: "",
    ...overrides,
  };
}

describe("the registration rules", () => {
  it("accepts a complete, valid form", () => {
    expect(validateRegistration(input())).toEqual({});
  });

  it("mirrors the server's password rule rather than inventing its own", () => {
    // The server asks for eight characters with a letter and a digit. Nothing
    // more: no symbol requirement, no mixed case, no rejected dictionary word.
    expect(
      validateRegistration(input({ password: "abcdefg1", confirmPassword: "abcdefg1" })),
    ).toEqual({});
    expect(
      validateRegistration(input({ password: "short1", confirmPassword: "short1" })).password,
    ).toBeDefined();
    expect(
      validateRegistration(input({ password: "alllettersx", confirmPassword: "alllettersx" }))
        .password,
    ).toBeDefined();
    expect(
      validateRegistration(input({ password: "12345678", confirmPassword: "12345678" })).password,
    ).toBeDefined();
  });

  it("measures the password in bytes, as bcrypt does", () => {
    // The server's 72 is a byte limit because bcrypt's is. Counting characters
    // here would accept a password the server rejects, for exactly the
    // students whose names and languages need more than one byte a letter.
    expect(passwordByteLength("café1234")).toBe(9);

    const long = "é".repeat(40) + "1a";
    expect(passwordByteLength(long)).toBeGreaterThan(72);
    expect(validateRegistration(input({ password: long, confirmPassword: long })).password).toMatch(
      /too long/i,
    );
  });

  it("reports every problem at once, not the first one", () => {
    const errors = validateRegistration(
      input({
        fullName: "A",
        email: "nope",
        password: "abc",
        confirmPassword: "xyz",
        gender: null,
      }),
    );

    expect(Object.keys(errors).sort()).toEqual([
      "confirm_password",
      "email",
      "full_name",
      "gender",
      "password",
    ]);
  });

  it("treats the class code as genuinely optional", () => {
    expect(validateRegistration(input({ classCode: "" })).class_code).toBeUndefined();
    expect(validateRegistration(input({ classCode: "  " })).class_code).toBeUndefined();
  });

  it("catches a mistyped confirmation, which no server can catch", () => {
    const errors = validateRegistration(input({ confirmPassword: "describe98" }));
    expect(errors.confirm_password).toBeDefined();
    expect(errors.password).toBeUndefined();
  });
});

describe("the password field", () => {
  it("shows the requirements before they are broken", async () => {
    const user = userEvent.setup();
    function Harness() {
      const [value, setValue] = React.useState("");
      return (
        <PasswordField
          id="password"
          label="Password"
          autoComplete="new-password"
          value={value}
          onChange={setValue}
          showChecklist
        />
      );
    }

    render(<Harness />);
    expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
    expect(screen.getByText(/a number/i)).toBeInTheDocument();

    await user.type(screen.getByLabelText("Password"), "describe99");
    expect(screen.getAllByText(/— met/)).toHaveLength(3);
  });

  it("reveals the password behind a button that says what it will do", async () => {
    const user = userEvent.setup();
    render(
      <PasswordField
        id="password"
        label="Password"
        autoComplete="current-password"
        value="secret123"
        onChange={() => {}}
      />,
    );

    const field = screen.getByLabelText("Password");
    expect(field).toHaveAttribute("type", "password");

    await user.click(screen.getByRole("button", { name: /show password/i }));
    expect(field).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: /hide password/i })).toBeInTheDocument();
  });
});

describe("the avatar set question", () => {
  it("is a real radio group, and says what it is for", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(<GenderChoice value={null} onChange={onChange} describedById="hint" />);

    const options = screen.getAllByRole("radio");
    expect(options).toHaveLength(2);
    expect(options.every((option) => option.getAttribute("aria-checked") === "false")).toBe(true);

    // Framed by what it does, not as a demographic field collected for its
    // own sake.
    expect(screen.getByText(/cartoon character that celebrates your results/i)).toBeInTheDocument();

    await user.click(options[0] as HTMLElement);
    expect(onChange).toHaveBeenCalledWith("female");
  });
});
