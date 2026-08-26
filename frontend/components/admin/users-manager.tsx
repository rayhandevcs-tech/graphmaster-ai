"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, Search, Users } from "lucide-react";

import { UserForm } from "./user-form";
import { EmptyState } from "@/components/layout/empty-state";
import { Pager } from "@/components/layout/pager";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FilterChips } from "@/components/ui/filter-chips";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { classesApi, errorMessage, queryKeys, usersApi } from "@/lib/api";
import { useAuth } from "@/lib/auth/context";
import { formatShortDate, initials } from "@/lib/format";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";
import type { UserListItem, UserRole } from "@/types/api";

/**
 * Everyone with an account.
 *
 * The most CRUD-shaped screen in the product and the one most at risk of
 * becoming an admin template, so it stays a list of *people*: name, what they
 * may do, which class, and whether they can sign in. No bulk selection, no
 * column chooser, no row of icon buttons — the one action is "open this person
 * and change something", and it opens a dialog that explains what each role
 * means.
 *
 * There is no delete. Accounts are deactivated: submissions, scores and XP
 * events all point at a user, and the ledger is append-only.
 */
const ROLES: { value: UserRole; label: string }[] = [
  { value: "student", label: "Students" },
  { value: "teacher", label: "Teachers" },
  { value: "admin", label: "Administrators" },
];

const PAGE_SIZE = 25;

export function UsersManager() {
  const { user: me } = useAuth();
  const [role, setRole] = useState<UserRole | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<UserListItem | null>(null);

  const debounced = useDebouncedValue(search, 300);
  const query = {
    role: role ?? undefined,
    search: debounced || undefined,
    page,
    page_size: PAGE_SIZE,
  };

  const users = useQuery({
    queryKey: queryKeys.users(query),
    queryFn: () => usersApi.list(query),
    placeholderData: (previous) => previous,
  });

  const classes = useQuery({
    queryKey: queryKeys.classes({ page_size: 100 }),
    queryFn: () => classesApi.list({ page_size: 100 }),
    staleTime: 5 * 60_000,
  });

  const rows = users.data?.items ?? [];
  const classNames = new Map((classes.data?.items ?? []).map((item) => [item.id, item.name]));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">People</h1>
        <p className="text-muted-foreground text-sm text-pretty">
          Roles, class assignment and whether an account can sign in. Accounts are deactivated
          rather than deleted — their work is still referenced.
        </p>
      </div>

      <div className="flex flex-col gap-4">
        <FilterChips
          label="Role"
          options={ROLES}
          value={role}
          onChange={(next) => {
            setRole(next);
            setPage(1);
          }}
          allLabel="Everyone"
        />

        <div className="relative max-w-sm">
          <Search
            className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
            aria-hidden
          />
          <Input
            value={search}
            placeholder="Search by name or email"
            aria-label="Search people"
            className="pl-9"
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
        </div>
      </div>

      <p role="status" className="text-muted-foreground text-sm">
        {users.data
          ? `${users.data.total.toLocaleString()} ${users.data.total === 1 ? "person" : "people"}.`
          : ""}
      </p>

      {users.isPending ? (
        <UsersSkeleton />
      ) : users.isError ? (
        <Alert variant="destructive">
          <AlertTitle>The user list could not be loaded</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <span>{errorMessage(users.error)}</span>
            <Button variant="outline" size="sm" onClick={() => void users.refetch()}>
              <RefreshCw aria-hidden />
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Users}
          title="Nobody matches"
          description="No account matches that search in this role."
        />
      ) : (
        <>
          <ul className="flex flex-col gap-2 md:hidden">
            {rows.map((row) => (
              <li key={row.id}>
                <Card className={`flex flex-col gap-2 p-4 ${row.is_active ? "" : "opacity-60"}`}>
                  <div className="flex items-center gap-3">
                    <Avatar className="size-9">
                      <AvatarFallback className="text-xs">{initials(row.full_name)}</AvatarFallback>
                    </Avatar>
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate text-sm font-medium">{row.full_name}</span>
                      <span className="text-muted-foreground truncate text-xs">{row.email}</span>
                    </span>
                  </div>
                  <p className="text-muted-foreground text-xs">
                    {roleLabel(row.role)}
                    {row.class_id ? ` · ${classNames.get(row.class_id) ?? "Class"}` : ""}
                    {row.is_active ? "" : " · deactivated"}
                  </p>
                  <Button variant="outline" size="sm" onClick={() => setEditing(row)}>
                    Change
                  </Button>
                </Card>
              </li>
            ))}
          </ul>

          <div className="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Person</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Class</TableHead>
                  <TableHead>Joined</TableHead>
                  <TableHead className="text-right">Status</TableHead>
                  <TableHead className="sr-only">Change</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id} className={row.is_active ? "" : "opacity-60"}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Avatar className="size-7">
                          <AvatarFallback className="text-[10px]">
                            {initials(row.full_name)}
                          </AvatarFallback>
                        </Avatar>
                        <span className="flex flex-col">
                          <span className="text-sm font-medium">
                            {row.full_name}
                            {row.id === me?.id ? (
                              <span className="text-muted-foreground font-normal"> · you</span>
                            ) : null}
                          </span>
                          <span className="text-muted-foreground text-xs">{row.email}</span>
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">{roleLabel(row.role)}</TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {row.class_id ? (classNames.get(row.class_id) ?? "—") : "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm whitespace-nowrap">
                      {formatShortDate(row.created_at)}
                    </TableCell>
                    <TableCell className="text-right text-sm">
                      {row.is_active ? (
                        <span className="text-success">Active</span>
                      ) : (
                        <span className="text-muted-foreground">Deactivated</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => setEditing(row)}>
                        Change
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {users.data && users.data.total_pages > 1 ? (
            <Pager
              page={users.data.page}
              totalPages={users.data.total_pages}
              total={users.data.total}
              onPageChange={setPage}
              itemNoun="people"
            />
          ) : null}
        </>
      )}

      {editing ? (
        <UserForm
          key={editing.id}
          user={editing}
          classes={classes.data?.items ?? []}
          isSelf={editing.id === me?.id}
          open
          onOpenChange={(next) => {
            if (!next) setEditing(null);
          }}
        />
      ) : null}
    </div>
  );
}

function roleLabel(role: UserRole): string {
  return role === "admin" ? "Administrator" : role === "teacher" ? "Teacher" : "Student";
}

function UsersSkeleton() {
  return (
    <div className="flex flex-col gap-2" aria-busy>
      <span className="sr-only" role="status">
        Loading the user list
      </span>
      {[0, 1, 2, 3, 4, 5].map((index) => (
        <Skeleton key={index} className="h-14 rounded-lg" />
      ))}
    </div>
  );
}
