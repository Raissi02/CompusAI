export type Role =
  | "candidate"
  | "academic_iit"
  | "academic_isb"
  | "interviewer"
  | "director"
  | "admin";

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  institution: "IIT" | "ISB" | null;
}

export interface Program {
  id: number;
  code: string;
  institution: "IIT" | "ISB";
  title: string;
  level: string;
  summary: string;
  duration: string;
  prerequisites: string;
  tuition: string;
  subjects: string[];
  careers: string[];
  source_url: string | null;
  is_sample: boolean;
  is_active: boolean;
}

export interface Profile {
  preferred_language: string;
  current_level: string;
  grades: Record<string, string>;
  interests: string[];
  goals: string;
  constraints: string;
  consent_at: string | null;
}

export interface Registration {
  id: number;
  candidate_id: number;
  program: Program;
  status: string;
  notes: string;
  created_at: string;
}

export interface Message {
  id: number;
  sender: "candidate" | "assistant";
  content: string;
  citations: { title: string; institution: string; is_sample: boolean; source_url: string }[];
  created_at: string;
}

export interface Appointment {
  id: number;
  user_id: number;
  starts_at: string;
  duration_minutes: number;
  mode: string;
  location: string;
  status: string;
  notes: string;
}

export interface QuestionnaireQuestion {
  id: string;
  category: string;
  type: "single" | "multi" | "text";
  question: string;
  options?: string[];
}

export interface Questionnaire {
  id: number;
  candidate_id?: number;
  program: Program;
  questions: QuestionnaireQuestion[];
  answers: Record<string, unknown>;
  completion_score?: number | null;
  summary?: string;
  submitted_at?: string | null;
}

export interface CandidateRecord {
  user: User;
  profile: Profile | null;
  preregistrations: Registration[];
}

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(init.headers);
  const isForm = typeof FormData !== "undefined" && init.body instanceof FormData;
  if (init.body && !isForm && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const authToken = token ?? (typeof window !== "undefined" ? sessionStorage.getItem("smartcampus_token") : null);
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  const guestToken = typeof window !== "undefined" ? sessionStorage.getItem("smartcampus_guest_token") : null;
  if (guestToken) headers.set("X-Guest-Token", guestToken);

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiError(
      `Could not connect to the API at ${API_URL}. Check that the backend is running.`,
      0,
    );
  }

  const raw = await response.text();
  let data: unknown;
  try {
    data = raw ? JSON.parse(raw) : null;
  } catch {
    data = raw;
  }
  if (!response.ok) {
    const detail =
      typeof data === "object" && data !== null && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : typeof data === "string" && data
          ? data
          : `Request failed with status ${response.status}.`;
    throw new ApiError(detail, response.status);
  }
  return data as T;
}

export const jsonBody = (value: unknown) => JSON.stringify(value);

export function roleLabel(role: Role): string {
  const labels: Record<Role, string> = {
    candidate: "Candidate",
    academic_iit: "IIT academic team",
    academic_isb: "ISB academic team",
    interviewer: "Interview team",
    director: "Admissions director",
    admin: "Platform administrator",
  };
  return labels[role];
}
