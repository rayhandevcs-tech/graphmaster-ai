# Software Requirements Specification — GraphMaster

**Version:** 1.0
**Document type:** IEEE 830-style SRS (adapted)
**Project type:** Final Year Project / Academic Research Prototype

---

## 1. Introduction

### 1.1 Purpose
This document specifies the requirements for **GraphMaster**, an AI-powered
gamified platform that helps university students improve their ability to
describe graphs and charts in academic English. It is the authoritative
requirements reference for the architecture documents in `docs/architecture/`
and for the sprint plan in `docs/PROJECT_PLAN.md`.

### 1.2 Scope
GraphMaster presents a student with a data visualisation, accepts a written
description either typed or as a photograph of handwriting, extracts text from
handwriting via OCR, measures the student's use of standard graph-description
vocabulary using NLP, scores the response, and returns animated gamified
feedback. Teachers monitor cohorts and export reports; administrators manage
platform content and users.

Out of scope for version 1.0: peer review between students, real-time
collaborative writing, mobile native applications, and languages other than
English.

### 1.3 Definitions

| Term | Meaning |
|---|---|
| **Target vocabulary** | The curated set of graph-description terms a given graph expects (see PROJECT_PLAN §3.2) |
| **Vocabulary percentage** | `(unique target terms detected ÷ total target terms) × 100` |
| **Reward tier** | Crown, Flower, Steady, or Hammer — determined by vocabulary percentage |
| **XP** | Experience points; drives levels and leaderboards |
| **Submission** | One student attempt at describing one graph |
| **Phrase term** | A multi-word vocabulary item such as *higher than* or *bottom out* |

### 1.4 Overview
Section 2 describes the product context. Section 3 lists functional
requirements. Section 4 lists non-functional requirements. Section 5 defines
user roles. Section 6 records assumptions and constraints.

---

## 2. Overall description

### 2.1 Product perspective
GraphMaster is a self-contained three-tier web application: a Next.js browser
client, a FastAPI application server, and a PostgreSQL database. OCR and NLP run
in-process within the application server (see PROJECT_PLAN §3.3). No external
paid service is required for full functionality.

### 2.2 Product functions
1. Account registration and authentication with role-based access
2. Gender-based avatar assignment and customisation
3. Graph practice sessions across four chart types
4. Typed answer submission
5. Handwritten answer submission via image upload and OCR
6. Vocabulary detection and scoring
7. Animated gamified reward feedback
8. XP, levels, achievements and badges
9. Global, class, weekly and monthly leaderboards
10. Student progress dashboard
11. Teacher monitoring dashboard with report export
12. Platform analytics

### 2.3 User characteristics
Students are university undergraduates with basic computer literacy and
intermediate English proficiency. Teachers are course instructors comfortable
with spreadsheet software. Administrators are technical staff.

### 2.4 Operating environment
Modern evergreen browsers (Chrome, Firefox, Safari, Edge) on desktop and mobile.
Server-side: Linux containers running Python 3.12 and Node.js 20+, PostgreSQL 16.

---

## 3. Functional requirements

Priority: **M** = Must have · **S** = Should have · **C** = Could have

### 3.1 Authentication and accounts

| ID | Requirement | Priority |
|---|---|---|
| FR-1.1 | The system shall allow a visitor to register with full name, email, password and gender | M |
| FR-1.2 | The system shall reject registration when the email is already in use | M |
| FR-1.3 | The system shall enforce a minimum password strength policy | M |
| FR-1.4 | The system shall store passwords only as salted hashes, never in plaintext or reversible form | M |
| FR-1.5 | The system shall issue a short-lived access token and a long-lived refresh token on successful login | M |
| FR-1.6 | The system shall rotate refresh tokens on use and invalidate the previous token | M |
| FR-1.7 | The system shall allow a user to log out, revoking the active refresh token | M |
| FR-1.8 | The system shall restrict each API endpoint to the roles authorised for it | M |
| FR-1.9 | The system shall allow a user to reset a forgotten password via an emailed token | S |

### 3.2 Avatars

| ID | Requirement | Priority |
|---|---|---|
| FR-2.1 | The system shall offer exactly two gender options: Male and Female | M |
| FR-2.2 | The system shall assign a cartoon boy avatar to male students and a cartoon girl avatar to female students on registration | M |
| FR-2.3 | The system shall display the student's avatar on the dashboard, result screen and leaderboard | M |
| FR-2.4 | The system shall animate the avatar during reward sequences | M |
| FR-2.5 | The system shall allow a student to select an alternative avatar of the same gender | C |

### 3.3 Graph practice

| ID | Requirement | Priority |
|---|---|---|
| FR-3.1 | The system shall support four graph types: line graph, bar chart, pie chart and area chart | M |
| FR-3.2 | The system shall render each graph from stored structured data rather than a static image | M |
| FR-3.3 | The system shall present each graph with a title, prompt and difficulty level | M |
| FR-3.4 | The system shall allow a student to filter available graphs by type and difficulty | S |
| FR-3.5 | The system shall allow a student to submit a description by typing it directly | M |
| FR-3.6 | The system shall allow a student to submit a description by uploading a photograph of handwriting | M |
| FR-3.7 | The system shall allow a student to re-attempt any graph | M |

### 3.4 OCR

| ID | Requirement | Priority |
|---|---|---|
| FR-4.1 | The system shall accept uploads in JPG, JPEG, PNG and WEBP format only | M |
| FR-4.2 | The system shall validate uploaded files by inspecting file signature bytes, not by file extension alone | M |
| FR-4.3 | The system shall reject uploads exceeding the configured maximum file size | M |
| FR-4.4 | The system shall attempt OCR providers in the order Google Vision, EasyOCR, Tesseract, skipping any provider that is unavailable | M |
| FR-4.5 | The system shall store both the original uploaded image and the extracted text | M |
| FR-4.6 | The system shall display the extracted text to the student for preview before analysis is performed | M |
| FR-4.7 | The system shall allow the student to correct the extracted text before submitting it for analysis | M |
| FR-4.8 | The system shall record which OCR provider produced the result and its confidence score | M |
| FR-4.9 | The system shall report a clear error when every OCR provider fails, without discarding the uploaded image | M |

### 3.5 Vocabulary library

| ID | Requirement | Priority |
|---|---|---|
| FR-5.1 | The system shall store at least 20 graph-description vocabulary terms in the database | M |
| FR-5.2 | The system shall organise vocabulary into the categories increase, decrease, fluctuation, stability, comparison, peak and lowest | M |
| FR-5.3 | The system shall support multi-word phrase terms such as *higher than* and *bottom out* | M |
| FR-5.4 | The system shall allow teachers to create, edit, deactivate and delete vocabulary terms | M |
| FR-5.5 | The system shall allow teachers to curate the target vocabulary set for each graph | M |
| FR-5.6 | The system shall apply a default target set derived from graph type when no set has been curated | M |

### 3.6 Analysis and scoring

| ID | Requirement | Priority |
|---|---|---|
| FR-6.1 | The system shall convert submitted text to lowercase and remove punctuation before analysis | M |
| FR-6.2 | The system shall match vocabulary by lemma, so that *increased*, *increasing* and *increase* all count as the term *increase* | M |
| FR-6.3 | The system shall detect multi-word phrase occurrences | M |
| FR-6.4 | The system shall count both total occurrences and unique terms detected | M |
| FR-6.5 | The system shall identify which target vocabulary terms are missing from the response | M |
| FR-6.6 | The system shall compute vocabulary percentage as `(detected ÷ total target) × 100` | M |
| FR-6.7 | The system shall compute a writing quality score from word count adequacy, lexical diversity, sentence structure and overview presence | M |
| FR-6.8 | The system shall compute the final score as `0.70 × vocabulary score + 0.30 × writing score` | M |
| FR-6.9 | The system shall persist the vocabulary score, writing score, final score and detected/missing term lists for every submission | M |
| FR-6.10 | The system shall generate written feedback naming the terms used and the terms missed | M |
| FR-6.11 | The system shall present a per-category breakdown of vocabulary usage | S |

### 3.7 Gamification

| ID | Requirement | Priority |
|---|---|---|
| FR-7.1 | The system shall assign a reward tier from the vocabulary percentage: Crown ≥90%, Flower 60–89%, Steady 50–59%, Hammer <50% | M |
| FR-7.2 | The system shall title a Crown-tier male student *Graph King* and a Crown-tier female student *Graph Queen* | M |
| FR-7.3 | The system shall play a crown, sparkle, confetti and victory-sound animation at Crown tier | M |
| FR-7.4 | The system shall play a rotating flower and positive-sound animation at Flower tier | M |
| FR-7.5 | The system shall play a cartoon hammer, dizzy, fall and recovery animation at Hammer tier | M |
| FR-7.6 | The Hammer animation shall remain humorous and shall never depict violence or humiliation | M |
| FR-7.7 | The system shall display the message *"Keep Practicing! You Can Improve!"* at Hammer tier | M |
| FR-7.8 | The system shall award the badge Royal Vocabulary Master, Rising Writer, Steady Learner or Practice Needed according to tier | M |
| FR-7.9 | The system shall allow the student to skip or replay any reward animation | M |
| FR-7.10 | The system shall respect the operating system `prefers-reduced-motion` setting | M |
| FR-7.11 | The system shall allow sound effects to be muted, and shall default to muted until the student opts in | M |

### 3.8 XP, levels and achievements

| ID | Requirement | Priority |
|---|---|---|
| FR-8.1 | The system shall award 20 XP for each completed submission | M |
| FR-8.2 | The system shall award a 30 XP bonus when the final score is 80 or above | M |
| FR-8.3 | The system shall award a 50 XP streak bonus once per calendar day for a maintained daily streak | M |
| FR-8.4 | The system shall record every XP award as an immutable ledger entry | M |
| FR-8.5 | The system shall support 100 levels derived deterministically from total XP | M |
| FR-8.6 | The system shall notify the student when a level is gained | M |
| FR-8.7 | The system shall unlock achievements including First Submission, 10/50/100 Submissions, Graph King, Graph Queen, Vocabulary Master, Consistency Champion and Perfect Score | M |
| FR-8.8 | The system shall award each achievement to a given user at most once | M |
| FR-8.9 | The system shall evaluate achievement rules from stored declarative definitions, so new achievements require no code change | S |

### 3.9 Leaderboards

| ID | Requirement | Priority |
|---|---|---|
| FR-9.1 | The system shall provide a global leaderboard across all students | M |
| FR-9.2 | The system shall provide a class leaderboard scoped to one cohort | M |
| FR-9.3 | The system shall provide weekly and monthly leaderboards | M |
| FR-9.4 | The system shall rank by XP, with average score and achievement count as tie-breakers | M |
| FR-9.5 | The system shall show the requesting student's own rank even when outside the visible page | S |

### 3.10 Student dashboard

| ID | Requirement | Priority |
|---|---|---|
| FR-10.1 | The dashboard shall display total attempts, average score and highest score | M |
| FR-10.2 | The dashboard shall display current XP, level and progress to the next level | M |
| FR-10.3 | The dashboard shall display earned achievements and badges | M |
| FR-10.4 | The dashboard shall display recent activity | M |
| FR-10.5 | The dashboard shall display a progress chart of score over time | M |

### 3.11 Teacher dashboard

| ID | Requirement | Priority |
|---|---|---|
| FR-11.1 | Teachers shall be able to view submissions from students in their classes | M |
| FR-11.2 | Teachers shall be able to view individual scores and full analysis breakdowns | M |
| FR-11.3 | Teachers shall be able to view class-level statistics | M |
| FR-11.4 | Teachers shall be able to view vocabulary usage reports across a class | M |
| FR-11.5 | Teachers shall be able to export reports as CSV, Excel and PDF | M |
| FR-11.6 | Teachers shall not be able to view submissions from classes they do not own | M |

### 3.12 Analytics

| ID | Requirement | Priority |
|---|---|---|
| FR-12.1 | The system shall report the most used vocabulary terms | M |
| FR-12.2 | The system shall report the least used vocabulary terms | M |
| FR-12.3 | The system shall report average class score | M |
| FR-12.4 | The system shall report vocabulary improvement trends over time | M |
| FR-12.5 | The system shall report student engagement statistics | M |
| FR-12.6 | The system shall present analytics as line, bar and pie charts | M |

---

## 4. Non-functional requirements

### 4.1 Performance

| ID | Requirement |
|---|---|
| NFR-1.1 | Non-OCR API responses shall complete within 500 ms at the 95th percentile under a load of 50 concurrent users |
| NFR-1.2 | NLP analysis of a 300-word response shall complete within 2 seconds |
| NFR-1.3 | OCR extraction of a single-page handwritten image shall complete within 10 seconds |
| NFR-1.4 | Leaderboard queries shall be served from materialised rankings, not computed per request |
| NFR-1.5 | First contentful paint shall occur within 2 seconds on a 3G connection |

### 4.2 Security

| ID | Requirement |
|---|---|
| NFR-2.1 | Passwords shall be hashed with bcrypt or Argon2 using a per-user salt |
| NFR-2.2 | All traffic shall be served over HTTPS in production |
| NFR-2.3 | Access tokens shall expire within 30 minutes |
| NFR-2.4 | Refresh tokens shall be stored hashed and shall be rotated on each use |
| NFR-2.5 | Authentication endpoints shall be rate limited per IP address |
| NFR-2.6 | Submission endpoints shall be rate limited per user |
| NFR-2.7 | All request bodies shall be validated against a schema before reaching business logic |
| NFR-2.8 | Uploaded files shall be validated by content signature and stored outside the web root with generated filenames |
| NFR-2.9 | Secrets shall be supplied via environment variables and shall never be committed to version control |
| NFR-2.10 | Database access shall use parameterised queries exclusively |

### 4.3 Reliability

| ID | Requirement |
|---|---|
| NFR-3.1 | Failure of one OCR provider shall not fail the request while another provider remains available |
| NFR-3.2 | A failed analysis shall leave the submission in an explicit `failed` state with a stored reason, never silently pending |
| NFR-3.3 | The XP ledger shall be append-only, making total XP fully reconstructable |
| NFR-3.4 | The application shall expose liveness and readiness endpoints |

### 4.4 Usability and accessibility

| ID | Requirement |
|---|---|
| NFR-4.1 | The interface shall be responsive from 320 px to 2560 px viewport width |
| NFR-4.2 | The interface shall provide a dark mode and shall honour the system colour scheme preference |
| NFR-4.3 | Colour contrast shall meet WCAG 2.1 AA |
| NFR-4.4 | All interactive elements shall be reachable and operable by keyboard |
| NFR-4.5 | All meaningful images and animations shall carry text alternatives |
| NFR-4.6 | Animations shall be reduced or disabled when `prefers-reduced-motion` is set |
| NFR-4.7 | Error messages shall state what went wrong and what the user can do next |

### 4.5 Maintainability

| ID | Requirement |
|---|---|
| NFR-5.1 | Backend code shall follow a layered architecture separating routers, services and repositories |
| NFR-5.2 | Automated test coverage of backend code shall be at least 80% |
| NFR-5.3 | Python code shall pass Black and Ruff; TypeScript shall pass ESLint and Prettier |
| NFR-5.4 | All schema changes shall be applied through versioned migrations |
| NFR-5.5 | The API shall be versioned by URL path prefix |

### 4.6 Portability

| ID | Requirement |
|---|---|
| NFR-6.1 | Every service shall ship as a Docker container |
| NFR-6.2 | The full stack shall start with a single `docker compose up` |
| NFR-6.3 | The system shall deploy without modification to a VPS, Render, Railway or DigitalOcean |
| NFR-6.4 | File storage shall be accessed through an abstraction allowing migration from local disk to cloud object storage without changes to business logic |

---

## 5. User roles and permissions

| Capability | Student | Teacher | Admin |
|---|:---:|:---:|:---:|
| Register and manage own profile | ✓ | ✓ | ✓ |
| Practise graphs and submit answers | ✓ | — | — |
| View own scores, XP and achievements | ✓ | ✓ | ✓ |
| View leaderboards | ✓ | ✓ | ✓ |
| View submissions of students in own classes | — | ✓ | ✓ |
| Manage vocabulary library | — | ✓ | ✓ |
| Create and manage graphs | — | ✓ | ✓ |
| Curate per-graph target vocabulary | — | ✓ | ✓ |
| Manage own classes and enrolments | — | ✓ | ✓ |
| Export class reports | — | ✓ | ✓ |
| View platform-wide analytics | — | — | ✓ |
| Manage all users and roles | — | — | ✓ |
| Manage all classes regardless of owner | — | — | ✓ |

---

## 6. Assumptions and constraints

### 6.1 Assumptions
1. Students have a device capable of photographing handwriting legibly.
2. All content is in English; no translation is provided.
3. Class enrolment is administered by teachers, not self-service.
4. A single PostgreSQL instance is sufficient for classroom-scale deployment.

### 6.2 Constraints
1. Google Vision requires paid credentials and is therefore optional; EasyOCR is the default provider.
2. OCR accuracy on handwriting is imperfect, which is why FR-4.7 makes the extracted text editable before analysis.
3. Vocabulary matching is lemma-based and does not perform full semantic
   similarity, so a synonym outside the curated library is not credited.
4. The project is an academic prototype; it is not certified for use as a formal
   assessment instrument of record.
