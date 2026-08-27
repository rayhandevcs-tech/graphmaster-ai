/**
 * Types mirroring the API schemas — generated, do not edit by hand.
 *
 * Source: GraphMaster 1.0.0 OpenAPI document.
 * Regenerate with `npm run api:types` against a running backend.
 *
 * Formats are aliased rather than erased: a `UUID` and a `DateTimeString` are
 * both strings to the compiler, but the alias says which one an endpoint wants.
 */

/** A UUID in canonical hyphenated form. */
export type UUID = string;
/** An ISO-8601 date, `YYYY-MM-DD`. */
export type DateString = string;
/** An ISO-8601 timestamp with an offset. */
export type DateTimeString = string;

/** The collection envelope every list endpoint returns (04-api-design §5.1). */
export interface Page<T> {
  items: T[];
  /** 1-indexed. */
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}


/** An achievement unlocked by one submission. */
export interface AchievementAwardOut {
  code: string;
  title: string;
  description: string;
  icon: string;
  xp_reward: number;
}

/**
 * A catalogue entry with this student's progress towards it.
 *
 * Progress is included for locked achievements because a visible distance —
 * "7 / 10" — is what makes the catalogue motivating rather than decorative.
 * Achievements that can never apply to the caller (the gendered crown pair)
 * are absent from the listing entirely rather than shown permanently locked.
 */
export interface AchievementOut {
  code: string;
  title: string;
  description: string;
  icon: string;
  xp_reward: number;
  is_unlocked: boolean;
  unlocked_at?: DateTimeString | null;
  progress: number;
  target: number;
  progress_percent: number;
}

/** Fields only an administrator may change. */
export interface AdminUserUpdateRequest {
  role?: UserRole | null;
  class_id?: UUID | null;
  is_active?: boolean | null;
}

/** Text to score against a graph's target vocabulary. */
export interface AnalysisRequest {
  /** The student's description of the graph */
  text: string;
}

/** Everything the results screen needs. */
export interface AnalysisResponse {
  graph_id: UUID;
  vocabulary_score: number;
  writing_score: number;
  final_score: number;
  vocabulary_percentage: number;
  /** Driven by the vocabulary percentage, not the final score (FR-7.1) */
  reward_tier: RewardTier;
  /** Every occurrence, repeats included */
  detected_count: number;
  unique_detected_count: number;
  /** Required targets only — the denominator of the percentage */
  total_target_count: number;
  bonus_terms_used: number;
  word_count: number;
  detected_terms: DetectedTermOut[];
  missing_terms: MissingTermOut[];
  category_breakdown: Record<string, CategoryUsageOut>;
  writing_breakdown: WritingBreakdownOut;
  feedback: FeedbackOut;
  engine_version: string;
}

/** Class or platform analytics (FR-11.3, FR-12.3, FR-12.5). */
export interface AnalyticsReport {
  scope: AnalyticsScope;
  class_id?: UUID | null;
  class_name?: string | null;
  date_from?: DateString | null;
  date_to?: DateString | null;
  submission_count: number;
  enrolled_student_count: number;
  active_student_count: number;
  average_final_score: number;
  average_vocabulary_percentage: number;
  highest_final_score: number;
  average_word_count: number;
  reward_tier_distribution: Record<string, number>;
  engagement: EngagementOut;
  trend: app__schemas__analytics__TrendPoint[];
  /** Empty for the platform scope, which has no roster */
  students?: StudentRow[];
}

export type AnalyticsScope = "platform" | "class" | "student";

export interface AnalyzerScoreReport {
  scope: string;
  class_id?: UUID | null;
  submission_count: number;
  summaries?: AnalyzerScoreSummary[];
}

/** One analyzer's mean, with the count it was taken over. */
export interface AnalyzerScoreSummary {
  analyzer: string;
  assessed_count: number;
  /** Null — never zero — when nothing in scope was assessed for this analyzer. A class whose grammar was never checked is not one that scored nothing. */
  average?: number | null;
}

/** How one analyzer's run ended, and what it measured. */
export interface AnalyzerStatusOut {
  /** `ok`, `unavailable` (not configured on this server), `skipped`, or `failed`. `unavailable` and `failed` are deliberately different: the first is a deployment fact and the second is a fault. */
  status: string;
  /** 0-100 diagnostic figure. Null where the analyzer produces none. */
  score?: number | null;
  issue_count?: number;
  duration_ms?: number;
  metrics?: Record<string, number>;
}

export interface AnalyzerTrendReport {
  scope: string;
  class_id?: UUID | null;
  analyzer: string;
  interval: string;
  /** Periods roll over together in this zone. */
  timezone: string;
  points?: app__schemas__assessment__TrendPoint[];
}

/** One finding, located in the student's own text. */
export interface AssessmentIssueOut {
  category: string;
  /** Stable slug, and the grouping key for class analytics. */
  subtype: string;
  /** `info` is a preference, not a mistake. */
  severity: string;
  original_text: string;
  /** Null where there is no single right answer. */
  suggested_text?: string | null;
  explanation: string;
  /** Half-open, into the submitted answer: `answer_text[start:end]` is the span. */
  start_index: number;
  end_index: number;
  confidence: number;
  /** Which analyzer found it. Never names a provider. */
  analyzer: string;
}

/** One submission's assessment, filtered to what the caller may see. */
export interface AssessmentResponse {
  submission_id: UUID;
  assessment_version: string;
  /** `complete`, `partial` (an analyzer failed), or `pending`. */
  status: string;
  /** Issues shown to this caller. */
  issue_count: number;
  /** Of those, the ones asserting a mistake. */
  error_count: number;
  /** Found but below this server's confidence floor. Counted, not shown. */
  suppressed_count: number;
  /** Categories where the per-submission cap dropped issues. */
  truncated_categories?: string[];
  /** Per-analyzer diagnostic scores. Null means the analyzer did not run here, which is a different fact from a score of zero. */
  scores?: Record<string, number | null>;
  analyzers?: Record<string, AnalyzerStatusOut>;
  issues?: AssessmentIssueOut[];
  assessed_at: DateTimeString;
}

export interface AssignmentCreate {
  class_id: UUID;
  graph_id: UUID;
  title: string;
  instructions?: string | null;
  due_at?: DateTimeString | null;
}

export interface AssignmentDetail {
  id: UUID;
  class_id: UUID;
  graph_id: UUID;
  title: string;
  instructions: string | null;
  /** Null means no deadline, which is not the same as overdue */
  due_at?: DateTimeString | null;
  is_active: boolean;
  created_at: DateTimeString;
  graph_title: string;
  graph_type: GraphType;
  class_name: string;
  submitted_count?: number | null;
  enrolled_count?: number | null;
  submission_id?: UUID | null;
  submission_status?: string | null;
  assigned_by: UUID | null;
  updated_at: DateTimeString;
}

/**
 * Who has done the work and who has not.
 *
 * Counted against **enrolment**, not against whoever happened to submit
 * (rule 35): a class where half the students never started must not read as
 * full marks. ``average_score`` is null rather than 0 when nothing has been
 * scored yet (rule 32).
 */
export interface AssignmentProgress {
  assignment: AssignmentSummary;
  enrolled_count: number;
  submitted_count: number;
  scored_count: number;
  late_count: number;
  average_score?: number | null;
  students: AssignmentStudentProgress[];
}

/** One enrolled student's standing against one assignment. */
export interface AssignmentStudentProgress {
  user_id: UUID;
  full_name: string;
  submission_id?: UUID | null;
  /** The submission's status, or null for a student who has not started */
  status?: string | null;
  /** Null until the submission is scored — never 0 (rule 32) */
  final_score?: number | null;
  submitted_at?: DateTimeString | null;
  /** Submitted after the deadline. Recorded, never punished. */
  is_late?: boolean;
}

/** One row in a task list, for a teacher or a student. */
export interface AssignmentSummary {
  id: UUID;
  class_id: UUID;
  graph_id: UUID;
  title: string;
  instructions: string | null;
  /** Null means no deadline, which is not the same as overdue */
  due_at?: DateTimeString | null;
  is_active: boolean;
  created_at: DateTimeString;
  graph_title: string;
  graph_type: GraphType;
  class_name: string;
  submitted_count?: number | null;
  enrolled_count?: number | null;
  submission_id?: UUID | null;
  submission_status?: string | null;
}

/**
 * Everything an assignment may become after it is set.
 *
 * ``class_id`` and ``graph_id`` are absent on purpose: moving an assignment
 * to another graph would silently change what the submissions already filed
 * against it were answering.
 */
export interface AssignmentUpdate {
  title?: string | null;
  instructions?: string | null;
  due_at?: DateTimeString | null;
  is_active?: boolean | null;
}

/** Returned by register and login. */
export interface AuthResponse {
  user: UserProfile;
  tokens: TokenPair;
}

export interface AvatarOut {
  id: UUID;
  code: string;
  name: string;
  gender: Gender;
  image_url: string;
  is_default: boolean;
  unlock_level: number;
}

export interface AvatarSelectRequest {
  avatar_id: UUID;
}

/**
 * An avatar annotated for the requesting user.
 *
 * `is_unlocked` is computed per request rather than stored: it depends on the
 * caller's level, so it is not a property of the avatar itself.
 */
export interface AvatarWithLock {
  id: UUID;
  code: string;
  name: string;
  gender: Gender;
  image_url: string;
  is_default: boolean;
  unlock_level: number;
  /** Whether the requesting user may select this avatar */
  is_unlocked: boolean;
  /** Whether this is the user's current avatar */
  is_selected: boolean;
}

/** The tier badge attached to one submission. */
export interface BadgeAwardOut {
  code: string;
  name: string;
  description: string;
  icon: string;
  reward_tier: RewardTier;
}

/** A reward-tier badge and how many times this student has earned it. */
export interface BadgeOut {
  code: string;
  name: string;
  description: string;
  icon: string;
  reward_tier: RewardTier;
  earned_count: number;
}

/** What one measure has looked like for this student until now. */
export interface BaselineOut {
  mean: number;
  /** Population standard deviation. Never divided into anything. */
  spread: number;
  /** Comparable prior submissions this was built from. */
  n: number;
  lowest: number;
  highest: number;
}

/** Per-category vocabulary usage (FR-6.11). */
export interface CategoryUsageOut {
  name: string;
  detected: string[];
  missing: string[];
  detected_count: number;
  target_count: number;
  percentage: number;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

/**
 * A Chart.js-compatible ``data`` object plus the axis metadata a
 * description needs.
 *
 * Axis labels are not decoration. "Sales in thousands of units" is the
 * vocabulary a student is expected to reuse; without it the same chart could
 * be describing anything.
 */
export interface ChartData {
  labels: string[];
  datasets: ChartDataset[];
  x_axis_label?: string | null;
  y_axis_label?: string | null;
  unit?: string | null;
  [key: string]: unknown;
}

/**
 * One series.
 *
 * Extra keys are allowed and stored verbatim: Chart.js accepts dozens of
 * styling options (``backgroundColor``, ``borderDash``, ``tension``…) and
 * enumerating them here would mean editing this model every time a teacher
 * wants a differently styled chart. JSON cannot carry functions, so nothing
 * executable can arrive this way.
 */
export interface ChartDataset {
  label: string;
  data: (number | null)[];
  [key: string]: unknown;
}

/**
 * A new class.
 *
 * ``code`` is optional. Teachers who already use a course code ("ENG201B")
 * keep it; everyone else gets a generated one.
 */
export interface ClassCreate {
  name: string;
  description?: string | null;
  code?: string | null;
}

export interface ClassDetail {
  id: UUID;
  name: string;
  code: string;
  description: string | null;
  teacher_id: UUID;
  is_active: boolean;
  student_count?: number;
  created_at: DateTimeString;
  teacher_name: string;
  updated_at: DateTimeString;
}

export interface ClassEnrolRequest {
  email: string;
}

export interface ClassJoinRequest {
  code: string;
}

/**
 * One roster row.
 *
 * Submission statistics (attempts, average score) join in at Sprint 6 when
 * the submissions table has rows; the gamification figures below are already
 * real.
 */
export interface ClassStudent {
  id: UUID;
  full_name: string;
  email: string;
  gender: string;
  avatar: AvatarOut | null;
  total_xp: number;
  current_level: number;
  current_streak_days: number;
  last_activity_date: DateString | null;
  is_active: boolean;
}

export interface ClassSummary {
  id: UUID;
  name: string;
  code: string;
  description: string | null;
  teacher_id: UUID;
  is_active: boolean;
  student_count?: number;
  created_at: DateTimeString;
}

export interface ClassUpdate {
  name?: string | null;
  description?: string | null;
  is_active?: boolean | null;
}

/**
 * How one submission's measurements sit against the student's own history.
 *
 * Observations for a teacher to read. The system draws no conclusion from
 * them, and two limits belong beside them wherever they are shown: the
 * platform's own feedback is the largest cause of the changes it measures,
 * and a settled profile is not evidence of anything, because a baseline can
 * itself be assisted.
 */
export interface ConsistencyResponse {
  submission_id: UUID;
  student_id: UUID;
  /** The comparison's version. Nothing is stored. */
  model_version: string;
  /** Prior submissions that passed every gate. */
  compared_count: number;
  /** Prior submissions looked at, gates included. */
  considered_count: number;
  /** How many prior submissions each gate excluded, and why. */
  excluded?: Record<string, number>;
  changes?: MeasureChangeOut[];
  /** Shown with the figures, not in a help page. */
  limitations?: string[];
}

export interface DetectedTermOut {
  term: string;
  lemma: string;
  category: string;
  category_name: string;
  is_required: boolean;
  count: number;
  matched_forms: string[];
  positions: number[][];
}

export type Difficulty = "beginner" | "intermediate" | "advanced";

/** Who is practising, and who has stopped (FR-12.5). */
export interface EngagementOut {
  enrolled_student_count: number;
  active_student_count: number;
  /** Enrolled students with no marked work in the period — counted against enrolment, not against whoever happened to submit */
  inactive_student_count: number;
  submissions_per_active_student: number;
  participation_rate: number;
  streak_holders: number;
  average_streak_days: number;
  longest_streak_days: number;
}

/**
 * The deployed rubric and the state of the language model.
 *
 * Published so the client can render the marking criteria from the server's
 * own configuration instead of hardcoding a copy that drifts out of step with
 * a retuned rubric.
 */
export interface EngineStatusResponse {
  available: boolean;
  engine_version: string;
  pipeline: PipelineOut;
  rubric: RubricOut;
}

/** What an upload produced, for the editable preview (FR-4.6, FR-4.7). */
export interface ExtractionResult {
  submission_id: UUID;
  status: SubmissionStatus;
  ocr_text: string;
  ocr_provider: OCRProviderName;
  ocr_confidence?: number | null;
  word_count: number;
  image_url?: string | null;
  /** Set for an empty or low-confidence read; never blocks the flow */
  warning?: string | null;
}

export interface FeedbackOut {
  headline: string;
  message: string;
  strengths: string[];
  improvements: string[];
  missing_by_category: Record<string, string[]>;
  next_step: string;
}

/**
 * XP, level, badge and achievements awarded for one submission.
 *
 * Delivered in the same payload as the score because the result screen
 * sequences one animation from both: the reward tier decides which animation
 * plays and the XP total decides what the bar counts up to, so splitting them
 * across two calls would render the reward before the bar knew its target.
 */
export interface GamificationOut {
  xp_awarded?: number;
  xp_breakdown?: XPBreakdownItem[];
  level_before?: number;
  level_after?: number;
  leveled_up?: boolean;
  /** Null only if the badge catalogue is unseeded — the award itself is unconditional, since every score has a tier */
  badge?: BadgeAwardOut | null;
  new_achievements?: AchievementAwardOut[];
  /** The practice streak after this submission, in days */
  streak_days?: number;
}

export type Gender = "male" | "female";

/** What a teacher or administrator receives: everything, plus the targets. */
export interface GraphAuthoringDetail {
  id: UUID;
  title: string;
  graph_type: GraphType;
  difficulty: Difficulty;
  is_published: boolean;
  image_url: string | null;
  /** Required target terms — the scoring denominator */
  target_vocabulary_count?: number;
  created_at: DateTimeString;
  prompt: string;
  chart_data: ChartData;
  reference_description: string | null;
  created_by: UUID;
  updated_at: DateTimeString;
  target_vocabulary?: TargetVocabularyOut[];
}

export interface GraphCreate {
  title: string;
  prompt: string;
  graph_type: GraphType;
  difficulty?: Difficulty;
  chart_data: ChartData;
  reference_description?: string | null;
  image_url?: string | null;
  target_vocabulary?: TargetVocabularyEntry[];
}

/**
 * What a student receives.
 *
 * ``reference_description`` is deliberately absent from this model rather
 * than merely omitted by the handler: it is a model answer, and a student who
 * could fetch it before submitting would be scored on their copying. Keeping
 * it out of the type makes the leak impossible rather than merely unlikely.
 * See docs/architecture/04-api-design.md §3.5.
 */
export interface GraphDetail {
  id: UUID;
  title: string;
  graph_type: GraphType;
  difficulty: Difficulty;
  is_published: boolean;
  image_url: string | null;
  /** Required target terms — the scoring denominator */
  target_vocabulary_count?: number;
  created_at: DateTimeString;
  prompt: string;
  chart_data: ChartData;
}

export interface GraphPublishRequest {
  is_published?: boolean;
}

export interface GraphSummary {
  id: UUID;
  title: string;
  graph_type: GraphType;
  difficulty: Difficulty;
  is_published: boolean;
  image_url: string | null;
  /** Required target terms — the scoring denominator */
  target_vocabulary_count?: number;
  created_at: DateTimeString;
}

export type GraphType = "line" | "bar" | "pie" | "area";

export interface GraphUpdate {
  title?: string | null;
  prompt?: string | null;
  graph_type?: GraphType | null;
  difficulty?: Difficulty | null;
  chart_data?: ChartData | null;
  reference_description?: string | null;
  image_url?: string | null;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export type InputMethod = "typed" | "handwriting";

export interface IssueFrequencyEntry {
  subtype: string;
  occurrences: number;
}

/** The commonest mistakes across a set of submissions. */
export interface IssueFrequencyReport {
  scope: string;
  class_id?: UUID | null;
  /** Submissions in scope that actually carry an assessment. */
  assessed_count: number;
  /** Submissions in scope, assessed or not. */
  submission_count: number;
  entries?: IssueFrequencyEntry[];
  counts_by_category?: Record<string, number>;
}

/**
 * One ranked student.
 *
 * Deliberately free of reward tiers. The board shows XP and level; a hammer
 * count is a private detail of one student's own results screen and
 * publishing it to their cohort is exactly the humiliation FR-7.6 rules out.
 */
export interface LeaderboardEntryOut {
  rank: number;
  user_id: UUID;
  full_name: string;
  avatar_url?: string | null;
  level: number;
  /** XP earned within this period, not lifetime */
  xp: number;
  average_score: number;
  submission_count: number;
  achievement_count: number;
  is_you?: boolean;
}

export interface LeaderboardPage {
  period: LeaderboardPeriod;
  entries: LeaderboardEntryOut[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface LeaderboardPeriod {
  scope: LeaderboardScope;
  class_id?: UUID | null;
  period_start: DateString;
  period_end: DateString;
  /** When these rankings were materialised. Null before the first build. */
  generated_at?: DateTimeString | null;
}

/** The caller's own standing, however far down the board (FR-9.5). */
export interface LeaderboardPosition {
  period: LeaderboardPeriod;
  /** Null when the caller has not practised in this period, so has no rank */
  entry?: LeaderboardEntryOut | null;
  total_ranked: number;
}

/** How many rows each scope produced. */
export interface LeaderboardRefreshOut {
  rebuilt: Record<string, number>;
}

export type LeaderboardScope = "global" | "class" | "weekly" | "monthly";

/** Where a student sits on the level curve (FR-8.5). */
export interface LevelOut {
  current_level: number;
  total_xp: number;
  xp_into_level: number;
  /** The span of the current level; 0 at the cap */
  xp_for_next_level: number;
  progress_percent: number;
  is_max_level: boolean;
  current_streak_days: number;
  longest_streak_days: number;
}

/** Where the user sits within their current level. */
export interface LevelProgress {
  current_level: number;
  total_xp: number;
  /** XP earned since reaching the current level */
  xp_into_level: number;
  /** XP span of the current level */
  xp_for_next_level: number;
  progress_percent: number;
  is_max_level: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface MeasureChangeOut {
  measure: string;
  /** Null where this submission has no figure for the measure. */
  current?: number | null;
  /** Null when there are too few comparable prior submissions — the normal state for most of a term. Renders as 'no baseline yet', never as zero and never as 'consistent'. */
  baseline?: BaselineOut | null;
  /** Current minus the baseline mean, in the measure's own units. Not a z-score. */
  difference?: number | null;
}

/** A plain acknowledgement for endpoints with nothing to return. */
export interface MessageResponse {
  message: string;
}

export interface MissingTermOut {
  term: string;
  lemma: string;
  category: string;
  category_name: string;
  is_required: boolean;
}

/** The editable preview handed back to the student (FR-4.6, FR-4.7). */
export interface OCRExtractionResponse {
  /** Cleaned text, ready to be edited and confirmed */
  text: string;
  provider: OCRProviderName;
  /** Mean provider confidence, 0.0–1.0, when reported */
  confidence?: number | null;
  word_count: number;
  /** The stored original, retained even when recognition fails */
  image_url?: string | null;
  /** Set for an empty or low-confidence read; never blocks the flow */
  warning?: string | null;
  /** Per-region text, confidence and bounding box, for debugging and research */
  blocks?: Record<string, unknown>[];
}

export type OCRProviderName = "google_vision" | "easyocr" | "tesseract";

export interface OCRProviderStatus {
  name: OCRProviderName;
  available: boolean;
}

/**
 * Which engines this server can actually use.
 *
 * Surfaced so the client can hide the handwriting-upload option entirely
 * when no engine is configured, rather than letting a student photograph a
 * page and only then discover it cannot be read.
 */
export interface OCRStatusResponse {
  /** Whether any engine is available */
  operational: boolean;
  providers: OCRProviderStatus[];
}

export interface PasswordResetConfirm {
  token: string;
  new_password: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PipelineOut {
  model: string;
  available: boolean;
  version?: string | null;
  pipes?: string[];
}

/**
 * Another user's profile.
 *
 * Deliberately omits email, class membership and activity dates: one student
 * browsing the leaderboard has no reason to learn another's contact details
 * or attendance pattern.
 */
export interface PublicUserProfile {
  id: UUID;
  full_name: string;
  gender: Gender;
  avatar?: AvatarOut | null;
  current_level: number;
  total_xp: number;
}

export interface RecentActivity {
  submission_id: UUID;
  graph_title: string;
  graph_type: GraphType;
  final_score: number;
  vocabulary_percentage: number;
  reward_tier: RewardTier;
  scored_at: DateTimeString;
}

/** Only needed by clients that cannot use the refresh cookie. */
export interface RefreshRequest {
  refresh_token?: string | null;
}

export interface RegisterRequest {
  full_name: string;
  email: string;
  password: string;
  gender: Gender;
  /** Optional class join code; enrols the student immediately. */
  class_code?: string | null;
}

/**
 * What this deployment can produce.
 *
 * Published so a client can hide an Excel button that would only ever return
 * 503, rather than offering it and apologising afterwards.
 */
export interface ReportCapabilities {
  formats: ReportFormat[];
  types: ReportType[];
  /** Ceiling on a raw submission export */
  max_rows: number;
}

export type ReportFormat = "csv" | "xlsx" | "pdf";

/** A generated export. */
export interface ReportOut {
  id: UUID;
  report_type: ReportType;
  format: ReportFormat;
  status: ReportStatus;
  class_id?: UUID | null;
  parameters?: Record<string, unknown>;
  /** Authenticated endpoint, not a static path — an export names students and their scores, so a guessable URL would be a disclosure */
  download_url?: string | null;
  error_message?: string | null;
  created_at: DateTimeString;
  completed_at?: DateTimeString | null;
}

/** Ask for one export (FR-11.5). */
export interface ReportRequest {
  report_type: ReportType;
  format?: ReportFormat;
  /** Required for a class summary unless the caller is an administrator */
  class_id?: UUID | null;
  /** Required for a student report */
  student_id?: UUID | null;
  date_from?: DateString | null;
  date_to?: DateString | null;
}

export type ReportStatus = "pending" | "ready" | "failed";

export type ReportType = "class_summary" | "student_detail" | "vocabulary_usage" | "submission_export";

export type RewardTier = "crown" | "flower" | "steady" | "hammer";

export interface RubricOut {
  vocabulary_weight: number;
  writing_weight: number;
  tier_thresholds: Record<string, number>;
  target_word_count: Record<string, number>;
}

/** A persisted score, as stored on the submission. */
export interface ScoreOut {
  vocabulary_score: number;
  writing_score: number;
  final_score: number;
  vocabulary_percentage: number;
  /** Every occurrence, repeats included */
  detected_count: number;
  unique_detected_count: number;
  /** Required targets at the time of scoring — the denominator of the percentage, frozen so a later edit to the graph cannot move a historical score */
  total_target_count: number;
  detected_terms: DetectedTermOut[];
  missing_terms: MissingTermOut[];
  category_breakdown: Record<string, CategoryUsageOut>;
  writing_breakdown: WritingBreakdownOut;
  /** Driven by the vocabulary percentage, not the final score (FR-7.1) */
  reward_tier: RewardTier;
  feedback: FeedbackOut;
  /** Fingerprints the rubric as well as the code, so two scores sharing a version are genuinely comparable */
  engine_version: string;
  scored_at: DateTimeString;
}

/**
 * Everything the student's home screen renders (FR-10.1 to FR-10.5).
 *
 * One payload rather than five, because it paints as a single screen: five
 * requests would show the XP bar, the streak and the chart arriving at
 * different moments, which reads as the page being broken rather than
 * loading.
 */
export interface StudentDashboard {
  total_attempts: number;
  average_score: number;
  highest_score: number;
  average_vocabulary_percentage: number;
  /** The student's own tier counts. Private to this screen — a hammer count never appears on a leaderboard (FR-7.6). */
  reward_tier_distribution: Record<string, number>;
  total_xp: number;
  current_level: number;
  xp_into_level: number;
  xp_for_next_level: number;
  level_progress_percent: number;
  current_streak_days: number;
  longest_streak_days: number;
  /** Unlocked only */
  achievements: AchievementOut[];
  badges: BadgeOut[];
  recent_activity: RecentActivity[];
  score_trend: app__schemas__analytics__TrendPoint[];
}

/** One student's rollup within a class report. */
export interface StudentRow {
  user_id: UUID;
  full_name: string;
  email: string;
  class_name?: string | null;
  total_xp: number;
  current_level: number;
  current_streak_days: number;
  longest_streak_days: number;
  submission_count: number;
  /** Null — not zero — for a student with no marked work */
  average_final_score?: number | null;
  average_vocabulary_percentage?: number | null;
  highest_final_score?: number | null;
  last_submission_at?: DateTimeString | null;
}

/**
 * The marking criteria a student may see (FR-6.12).
 *
 * A separate model from :class:`RubricOut`, not a subset view of it. The two
 * are shaped by different questions — "what does this server score with" and
 * "what may a learner be told" — and a shared model would answer the second
 * with whatever the first happened to grow.
 *
 * Absent on purpose: the tier thresholds (writing to the number is not
 * describing a chart), the engine version and the language-model state
 * (deployment facts), and the target vocabulary, which belongs to a graph and
 * never reaches this endpoint at all.
 */
export interface StudentRubricOut {
  /** Share of the final score carried by target vocabulary, as a fraction */
  vocabulary_weight: number;
  /** Share carried by the writing-quality signal */
  writing_weight: number;
  target_word_count: WordCountBand;
}

/** Open an attempt at a graph. */
export interface SubmissionCreate {
  graph_id: UUID;
  /** `typed` to write in the browser, `handwriting` to photograph a page */
  input_method?: InputMethod;
  /** The assignment this attempt is for. Omit for free practice — scoring, XP, tiers and the leaderboard are identical either way. */
  assignment_id?: UUID | null;
}

/** One submission with everything the client needs to render it. */
export interface SubmissionDetail {
  id: UUID;
  graph_id: UUID;
  graph_title?: string | null;
  graph_type?: GraphType | null;
  /** Null for free practice, which is most of them */
  assignment_id?: UUID | null;
  assignment_title?: string | null;
  user_id: UUID;
  student_name?: string | null;
  input_method: InputMethod;
  status: SubmissionStatus;
  answer_text?: string | null;
  word_count: number;
  /** The unedited machine reading, kept alongside the corrected answer */
  ocr_text?: string | null;
  ocr_provider?: OCRProviderName | null;
  ocr_confidence?: number | null;
  was_ocr_edited?: boolean;
  has_image?: boolean;
  /** Authenticated endpoint, not a static path — fetch it with the bearer token and render the blob */
  image_url?: string | null;
  error_message?: string | null;
  submitted_at: DateTimeString;
  scored_at?: DateTimeString | null;
  score?: ScoreOut | null;
  /** The model answer. Released once the attempt is scored, and to teachers at any time. */
  reference_description?: string | null;
}

/** The response to scoring a submission. */
export interface SubmissionResult {
  submission: SubmissionDetail;
  score: ScoreOut;
  gamification: GamificationOut;
  /** Released here because the attempt is now marked */
  reference_description?: string | null;
}

export type SubmissionStatus = "draft" | "extracting" | "extracted" | "analyzing" | "scored" | "failed";

/** One row in a listing. */
export interface SubmissionSummary {
  id: UUID;
  graph_id: UUID;
  graph_title?: string | null;
  graph_type?: GraphType | null;
  /** Null for free practice. Present so a client resuming a draft can tell an attempt at an assignment apart from one the student chose themselves. */
  assignment_id?: UUID | null;
  user_id: UUID;
  student_name?: string | null;
  input_method: InputMethod;
  status: SubmissionStatus;
  word_count: number;
  final_score?: number | null;
  vocabulary_percentage?: number | null;
  reward_tier?: RewardTier | null;
  submitted_at: DateTimeString;
  scored_at?: DateTimeString | null;
}

/** Set or correct the answer before analysis (FR-4.7). */
export interface SubmissionTextUpdate {
  /** The student's description of the graph */
  text: string;
}

/** The target set a submission would actually be scored against. */
export interface TargetSummaryResponse {
  graph_id: UUID;
  /** 'curated' when a teacher set the list, 'default' when derived from the chart type (FR-5.6) */
  source: string;
  required_count: number;
  optional_count: number;
  terms: TargetTermOut[];
}

export interface TargetTermOut {
  term: string;
  lemma: string;
  category: string;
  category_name: string;
  is_required: boolean;
  is_phrase: boolean;
  weight: number;
}

export interface TargetVocabularyEntry {
  vocabulary_item_id: UUID;
  /** Required terms form the denominator of the vocabulary percentage. Optional terms are credited when used but do not make the crown tier harder to reach. */
  is_required?: boolean;
}

export interface TargetVocabularyOut {
  is_required: boolean;
  item: VocabularyItemOut;
}

/** The full target set. This replaces whatever was there before. */
export interface TargetVocabularyReplace {
  items: TargetVocabularyEntry[];
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type?: string;
  /** Access token lifetime in seconds */
  expires_in: number;
}

export interface TrendReport {
  scope: AnalyticsScope;
  class_id?: UUID | null;
  granularity: string;
  date_from?: DateString | null;
  date_to?: DateString | null;
  points: app__schemas__analytics__TrendPoint[];
}

/** A row in the administrator's user list. */
export interface UserListItem {
  id: UUID;
  email: string;
  full_name: string;
  role: UserRole;
  gender: Gender;
  class_id?: UUID | null;
  total_xp: number;
  current_level: number;
  is_active: boolean;
  created_at: DateTimeString;
}

/** The caller's own profile. */
export interface UserProfile {
  id: UUID;
  email: string;
  full_name: string;
  role: UserRole;
  gender: Gender;
  avatar?: AvatarOut | null;
  class_id?: UUID | null;
  total_xp: number;
  current_level: number;
  current_streak_days: number;
  longest_streak_days: number;
  last_activity_date?: DateString | null;
  is_active: boolean;
  created_at: DateTimeString;
}

export type UserRole = "student" | "teacher" | "admin";

export interface UserUpdateRequest {
  full_name?: string | null;
  avatar_id?: UUID | null;
}

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

export interface VocabularyBulkCreateRequest {
  items: VocabularyItemCreate[];
}

/**
 * The outcome of a bulk import.
 *
 * Duplicates are skipped rather than failing the whole request: a teacher
 * pasting forty terms where three already exist should not lose the other
 * thirty-seven.
 */
export interface VocabularyBulkResult {
  created: VocabularyItemOut[];
  skipped: VocabularySkipped[];
  created_count: number;
  skipped_count: number;
}

export interface VocabularyCategoryOut {
  id: UUID;
  code: string;
  name: string;
  description: string | null;
  display_order: number;
  /** Active terms in this category */
  item_count?: number;
}

/**
 * A new term.
 *
 * ``is_phrase`` is deliberately absent: it is derived from whether the term
 * contains whitespace, so the flag can never disagree with the term itself.
 * ``lemma`` defaults to the lowercased term, which is correct for the common
 * single-word case; a teacher adding an irregular form ("higher than" →
 * "high than") supplies it explicitly.
 */
export interface VocabularyItemCreate {
  category_code: string;
  term: string;
  lemma?: string | null;
  weight?: number;
}

export interface VocabularyItemOut {
  id: UUID;
  term: string;
  lemma: string;
  is_phrase: boolean;
  weight: number;
  is_active: boolean;
  category_id: UUID;
  category_code: string;
  category_name: string;
  created_at: DateTimeString;
  updated_at: DateTimeString;
}

/**
 * A partial update. Every field is optional; omitted fields are untouched.
 *
 * ``is_active`` is settable here so a soft-deleted term can be restored;
 * ``DELETE`` only ever sets it false.
 */
export interface VocabularyItemUpdate {
  category_code?: string | null;
  term?: string | null;
  lemma?: string | null;
  weight?: number | null;
  is_active?: boolean | null;
}

export interface VocabularySkipped {
  term: string;
  reason: string;
}

/** Most and least used target terms (FR-12.1, FR-12.2). */
export interface VocabularyUsageReport {
  scope: AnalyticsScope;
  class_id?: UUID | null;
  date_from?: DateString | null;
  date_to?: DateString | null;
  term_count: number;
  used_term_count: number;
  /** Curated terms nobody reached for at all — invisible to any report built only from what students did write */
  unused_term_count: number;
  most_used: VocabularyUsageRow[];
  /** Least used first */
  least_used: VocabularyUsageRow[];
}

export interface VocabularyUsageRow {
  term: string;
  lemma: string;
  category: string;
  category_name: string;
  /** Total occurrences, repeats included */
  uses: number;
  submission_count: number;
  student_count: number;
}

/** The answer length the task expects. */
export interface WordCountBand {
  min: number;
  max: number;
}

/**
 * The evidence behind the writing score.
 *
 * Exposed rather than hidden because the score is a heuristic and a teacher
 * disputing it deserves to see what it measured.
 */
export interface WritingBreakdownOut {
  word_count: number;
  sentence_count: number;
  components: WritingComponentsOut;
  measures: WritingMeasuresOut;
}

export interface WritingComponentsOut {
  word_count: number;
  lexical_diversity: number;
  sentence_structure: number;
  overview: number;
}

export interface WritingMeasuresOut {
  mattr: number;
  mean_sentence_length: number;
  subordination_ratio: number;
  has_overview: boolean;
  overview_sentence_index?: number | null;
}

/** An administrative correction to a student's XP (§8 of the design). */
export interface XPAdjustment {
  user_id: UUID;
  /** Signed XP to add. Negative offsets an earlier over-award. */
  amount: number;
  /** Why the adjustment was made. Mandatory: an unexplained change is indistinguishable from tampering once the data is used as evidence. */
  note: string;
}

/** One line of the XP a single submission earned. */
export interface XPBreakdownItem {
  reason: XPReason;
  amount: number;
}

/** One entry in the append-only ledger. */
export interface XPEventOut {
  id: UUID;
  /** Signed. A negative amount is an administrative correction — the ledger is never edited, so an over-award is offset rather than removed. */
  amount: number;
  reason: XPReason;
  /** The calendar day in the platform timezone this event belongs to */
  event_date: DateString;
  submission_id?: UUID | null;
  achievement_code?: string | null;
  note?: string | null;
  created_at: DateTimeString;
}

export type XPReason = "submission" | "high_score_bonus" | "streak_bonus" | "achievement" | "manual_adjustment";

/** One bucket of the score trend (FR-10.5, FR-12.4). */
export interface app__schemas__analytics__TrendPoint {
  date: DateString;
  submission_count: number;
  average_final_score: number;
  average_vocabulary_percentage: number;
}

/** One period of a trend line. */
export interface app__schemas__assessment__TrendPoint {
  period: DateString;
  assessed_count: number;
  /** Null where nothing in the period was assessed. The line **breaks** here; it is never interpolated, because bridging the gap would draw a step change on the day the engine was switched on and read as a real one. */
  average?: number | null;
}



/* Paged collections. */

export type PageAssignmentSummary = Page<AssignmentSummary>;

export type PageClassSummary = Page<ClassSummary>;

export type PageGraphSummary = Page<GraphSummary>;

export type PageReportOut = Page<ReportOut>;

export type PageSubmissionSummary = Page<SubmissionSummary>;

export type PageUserListItem = Page<UserListItem>;

export type PageVocabularyItemOut = Page<VocabularyItemOut>;

export type PageXPEventOut = Page<XPEventOut>;

