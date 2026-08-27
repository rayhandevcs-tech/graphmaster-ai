# Sprint 22 Design Note — Assignments

Short by intent: one table, one nullable column, no new concept beyond the one
missing word.

## 1. What is already here

**Sections need nothing.** `classes` has `teacher_id`, so a faculty member who
teaches four sections makes four classes, each with its own join code, and
`users.class_id` puts a student in exactly one. Every teaching screen is
already scoped by class, and the leaderboard already has a `class` board. No
new model, no migration.

What is missing is the sentence *"Section A must describe this graph by
Friday."* The product has graphs, and it has classes, and nothing that joins
them with an expectation attached.

## 2. The table

```
assignments
  id            uuid  pk
  class_id      uuid  fk classes(id)   on delete cascade
  graph_id      uuid  fk graphs(id)    on delete restrict
  title         text                    -- "Week 3 · rainfall"
  instructions  text  null              -- what the teacher said in the lesson
  due_at        timestamptz null        -- null means "no deadline", not "overdue"
  assigned_by   uuid  fk users(id)      on delete set null
  is_active     bool  default true
  created_at / updated_at
```

`on delete restrict` on `graph_id` matters: a graph with assignments against it
must not vanish underneath a student's submission history. Graphs are already
undeletable once attempted; this extends the same protection.

**One index**, `(class_id, is_active, due_at)`, because the only hot read is
"what is this class's open work, soonest first".

**No unique constraint on `(class_id, graph_id)`.** Setting the same graph
again next term is legitimate, and a partial unique index over `is_active`
would block a teacher re-opening work they closed by accident.

## 3. The link to submissions

`submissions.assignment_id`, **nullable**, `on delete set null`.

Nullable is the whole design. Free practice is the product's core loop and must
keep working exactly as it does — a student who picks a graph from the library
creates a submission with no assignment, and nothing about scoring, XP, tiers
or the leaderboard changes. An assignment only *labels* work that was done for
one.

Set once, at submission creation, from the assignment the student opened.
Never updated: a scored submission is frozen (rule 19), and re-pointing one at
a different assignment would move a mark between two pieces of work.

`on delete set null` rather than cascade — deleting an assignment must never
delete a student's writing.

## 4. What it does *not* do

- **No scoring change.** The rubric, the tier, the XP award and the leaderboard
  are untouched. An assignment is a due date and a label.
- **No lock-out.** A passed deadline does not refuse a submission; it marks it
  late. Refusing work a student finally sat down to do is the opposite of what
  this platform is for.
- **No new grading path.** Teachers already read submissions; the assignment
  gives that list a filter and a denominator ("18 of 30 have submitted").

## 5. API

Five operations, all under the existing `/classes` authorisation rule — a class
you do not teach is refused with 403, never returned empty (rule 33).

| Method | Path | Who |
|---|---|---|
| `POST` | `/assignments` | teacher, admin |
| `GET` | `/assignments` | teacher sees their classes'; a student sees their own class's |
| `GET` | `/assignments/{id}` | as above |
| `PATCH` | `/assignments/{id}` | teacher, admin — title, instructions, due date, active |
| `GET` | `/assignments/{id}/progress` | teacher, admin — who has submitted, who has not |

`progress` counts against **enrolment**, not against whoever submitted
(rule 35): "12 of 30" and the twelve names, not "12 submissions".

## 6. Order

1. Migration, models — *this commit*
2. Repository, service, schemas, router, tests
3. Teacher: assign a graph, see progress
4. Student: "due this week" on the dashboard and the practice library
5. Docs
