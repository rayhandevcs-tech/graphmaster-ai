"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { errorMessage, queryKeys, usersApi } from "@/lib/api";
import type { ClassSummary, UserListItem, UserRole } from "@/types/api";

/**
 * Changing what someone may do.
 *
 * The only genuinely dangerous action in this product, and the reason it is
 * behind a dialog rather than an inline dropdown: a role changed by a
 * mis-tapped select is discovered when a teacher can no longer open their own
 * class.
 *
 * **An administrator cannot remove their own administrator role here**, and
 * the reason is stated rather than the control being quietly disabled. The
 * server would let them; the last administrator on a deployment doing it
 * locks everyone out of user management with no way back through the
 * interface. Someone else with the role can still do it for them, which is the
 * correct shape for that decision.
 */
const ROLES: { value: UserRole; label: string; hint: string }[] = [
  { value: "student", label: "Student", hint: "Practises, and appears on the leaderboard." },
  { value: "teacher", label: "Teacher", hint: "Runs classes, authors graphs, reads analytics." },
  {
    value: "admin",
    label: "Administrator",
    hint: "Everything a teacher can do, plus this screen.",
  },
];

export function UserForm({
  user,
  classes,
  isSelf,
  open,
  onOpenChange,
}: {
  user: UserListItem;
  classes: ClassSummary[];
  /** True when this row is the signed-in administrator. */
  isSelf: boolean;
  open: boolean;
  onOpenChange: (next: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [role, setRole] = useState<UserRole>(user.role);
  const [classId, setClassId] = useState(user.class_id ?? "");
  const [active, setActive] = useState(user.is_active);

  const wouldDemoteSelf = isSelf && user.role === "admin" && role !== "admin";
  const wouldDeactivateSelf = isSelf && !active;
  const blocked = wouldDemoteSelf || wouldDeactivateSelf;

  const save = useMutation({
    mutationFn: () =>
      usersApi.adminUpdate(user.id, {
        role,
        class_id: role === "student" ? classId || null : null,
        is_active: active,
      }),
    onSuccess: async () => {
      onOpenChange(false);
      await queryClient.invalidateQueries({ queryKey: queryKeys.users() });
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{user.full_name}</DialogTitle>
          <DialogDescription>{user.email}</DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="user-role">Role</Label>
            <Select
              id="user-role"
              value={role}
              onChange={(event) => setRole(event.target.value as UserRole)}
            >
              {ROLES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
            <p className="text-muted-foreground text-xs">
              {ROLES.find((option) => option.value === role)?.hint}
            </p>
          </div>

          {role === "student" ? (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="user-class">Class</Label>
              <Select
                id="user-class"
                value={classId}
                onChange={(event) => setClassId(event.target.value)}
              >
                <option value="">No class</option>
                {classes.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </Select>
            </div>
          ) : null}

          <div className="flex items-center justify-between gap-4">
            <div className="flex flex-col">
              <span className="text-sm font-medium">Account active</span>
              <span className="text-muted-foreground text-xs text-pretty">
                A deactivated account cannot sign in. Their work and scores are kept.
              </span>
            </div>
            <Switch checked={active} onCheckedChange={setActive} label="Account active" />
          </div>

          {wouldDemoteSelf ? (
            <Alert variant="info">
              <AlertTitle>You cannot remove your own administrator role</AlertTitle>
              <AlertDescription>
                If this is the last administrator account, nobody could reach this screen again. Ask
                another administrator to change it for you.
              </AlertDescription>
            </Alert>
          ) : null}

          {wouldDeactivateSelf ? (
            <Alert variant="info">
              <AlertTitle>You cannot deactivate your own account</AlertTitle>
              <AlertDescription>You would be signed out with no way back in.</AlertDescription>
            </Alert>
          ) : null}

          {save.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{errorMessage(save.error)}</AlertDescription>
            </Alert>
          ) : null}
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">
              Cancel
            </Button>
          </DialogClose>
          <Button onClick={() => save.mutate()} disabled={blocked || save.isPending}>
            {save.isPending ? "Saving…" : "Save changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
