"use client";

import {
  Badge,
  Button,
  Card,
  Checkbox,
  Dialog,
  Flex,
  Heading,
  Select,
  Separator,
  Spinner,
  Table,
  Text,
  TextArea,
  TextField,
} from "@radix-ui/themes";
import {
  FormEvent,
  ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  api,
  ApiError,
  Appointment,
  CandidateRecord,
  jsonBody,
  Message,
  Program,
  Profile,
  Questionnaire,
  Registration,
  Role,
  roleLabel,
  User,
} from "@/lib/api";

type View = "overview" | "conversation" | "programmes" | "journey" | "candidates" | "knowledge";

type Stats = {
  candidates: number;
  conversations: number;
  preregistrations: number;
  appointments: number;
  registrations_by_status: Record<string, number>;
  preregistrations_by_institution: Record<string, number>;
  data_note: string;
};

type Recommendation = {
  program: Program;
  interest_overlap: number;
  matched_interests: string[];
  explanation: string;
  score_note: string;
  requires_human_review: boolean;
};

const emptyProfile: Profile = {
  preferred_language: "fr",
  current_level: "",
  grades: {},
  interests: [],
  goals: "",
  constraints: "",
  consent_at: null,
};

const interestOptions = [
  "Informatique",
  "Mathématiques",
  "Sciences",
  "Gestion",
  "Économie",
  "Ingénierie",
];

const statusNames: Record<string, string> = {
  pending_review: "Awaiting review",
  needs_information: "More information requested",
  approved: "Academic review complete",
  rejected: "Closed by academic team",
  proposed: "Awaiting your response",
  confirmed: "Confirmed",
  declined: "Declined",
};

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

function dateLabel(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function Label({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label className="field-label" htmlFor={htmlFor}>
      {children}
    </label>
  );
}

function Field({
  label,
  id,
  children,
  hint,
}: {
  label: string;
  id: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <div className="field">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <Text as="p" size="1" color="gray">{hint}</Text>}
    </div>
  );
}

function StatusBadge({ value, sample = false }: { value: string; sample?: boolean }) {
  return (
    <Flex gap="2" wrap="wrap" align="center">
      <Badge color={value === "approved" || value === "confirmed" ? "green" : value === "rejected" ? "red" : "blue"} variant="soft">
        {statusNames[value] ?? value.replaceAll("_", " ")}
      </Badge>
      {sample && <Badge color="amber" variant="soft">Sample data</Badge>}
    </Flex>
  );
}

function AuthScreen({
  onLogin,
  onStartGuest,
  onBackToGuest,
  hasGuestConversation,
}: {
  onLogin: (user: User, token: string) => void;
  onStartGuest: () => void;
  onBackToGuest: () => void;
  hasGuestConversation: boolean;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const path = mode === "login" ? "/api/auth/login" : "/api/auth/register";
      const result = await api<{ access_token: string; user: User }>(path, {
        method: "POST",
        body: jsonBody(mode === "login" ? { email, password } : { name, email, password }),
      });
      onLogin(result.user, result.access_token);
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page" id="main-content">
      <a className="skip-link" href="#auth-form">Skip to sign in</a>
      <section className="auth-copy">
        <a className="brand-lockup" href="/" aria-label="SmartCampus AI home">
          <span className="brand-mark">S</span>
          <span>SmartCampus <b>AI</b></span>
        </a>
        <div className="auth-intro">
          <Badge color="blue" variant="soft">University orientation</Badge>
          <Heading size="8" className="auth-heading">A clearer path to your next step.</Heading>
          <Text as="p" size="4" color="gray">
            Explore study options, talk through your interests, and prepare for a conversation with an admissions adviser.
          </Text>
          <div className="auth-points">
            <div><span className="point-index">01</span><span>Explore programmes from one place</span></div>
            <div><span className="point-index">02</span><span>Build an orientation profile as you go</span></div>
            <div><span className="point-index">03</span><span>Keep academic decisions with people</span></div>
          </div>
        </div>
        <Text size="1" color="gray" className="auth-footnote">Sample programme information is clearly marked and must be replaced with verified IIT and ISB sources.</Text>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <Text size="2" color="gray" className="auth-eyebrow">{mode === "login" ? "Your application workspace" : "New candidate account"}</Text>
          <Heading size="6">{mode === "login" ? "Welcome back" : "Create your account"}</Heading>
          <Text as="p" size="2" color="gray">
            {mode === "login" ? "Sign in to continue your orientation." : "Create an account to save your progress and continue your orientation."}
          </Text>
          <form className="stack-form auth-form" id="auth-form" onSubmit={submit} aria-busy={busy}>
            {mode === "register" && (
              <Field label="Full name" id="auth-name">
                <TextField.Root id="auth-name" autoComplete="name" placeholder="Your full name" required minLength={2} value={name} onChange={(event) => setName(event.target.value)} />
              </Field>
            )}
            <Field label="Email address" id="auth-email">
              <TextField.Root id="auth-email" type="email" autoComplete="email" placeholder="you@example.com" required value={email} onChange={(event) => setEmail(event.target.value)} />
            </Field>
            <Field label="Password" id="auth-password" hint={mode === "register" ? "At least 12 characters." : undefined}>
              <div className="password-control">
                <TextField.Root id="auth-password" type={showPassword ? "text" : "password"} autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={mode === "register" ? 12 : 1} value={password} onChange={(event) => setPassword(event.target.value)} />
                <button className="password-toggle" type="button" aria-pressed={showPassword} onClick={() => setShowPassword((visible) => !visible)}>
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </Field>
            {error && <p className="inline-error" role="alert">{error}</p>}
            <Button type="submit" size="3" disabled={busy} aria-busy={busy}>
              {busy ? <Spinner /> : mode === "login" ? "Sign in" : "Create account"}
            </Button>
          </form>
          <div className="auth-mode-switch">
            <Text size="2" color="gray">
              {mode === "login" ? "New to the platform?" : "Already have an account?"}
            </Text>
            <button type="button" className="text-button" disabled={busy} onClick={() => { setError(""); setPassword(""); setShowPassword(false); setMode(mode === "login" ? "register" : "login"); }}>
              {mode === "login" ? "Create an account" : "Sign in"}
            </button>
          </div>
          <Separator size="4" />
          {hasGuestConversation ? (
            <Button type="button" className="auth-guest-button" variant="soft" onClick={onBackToGuest}>Return to my guest conversation</Button>
          ) : (
            <Button type="button" className="auth-guest-button" variant="soft" onClick={onStartGuest}>Explore as a guest</Button>
          )}
        </div>
      </section>
    </main>
  );
}

function GuestChat({ onCreateAccount }: { onCreateAccount: () => void }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const begin = useCallback(async () => {
    setError("");
    try {
      const session = await api<{ id: string; token: string; conversation_id: number; expires_at: string }>("/api/guest/sessions", { method: "POST" });
      sessionStorage.setItem("smartcampus_guest_id", session.id);
      sessionStorage.setItem("smartcampus_guest_token", session.token);
      setSessionId(session.id);
      setConversationId(session.conversation_id);
      setMessages([]);
    } catch (caught) {
      setError(messageOf(caught));
    }
  }, []);

  useEffect(() => {
    let active = true;
    const savedId = sessionStorage.getItem("smartcampus_guest_id");
    const savedToken = sessionStorage.getItem("smartcampus_guest_token");
    if (!savedId || !savedToken) {
      void begin();
      return () => { active = false; };
    }
    setSessionId(savedId);
    void api<{ conversation_id: number; messages: Message[] }>(`/api/guest/sessions/${savedId}`)
      .then((session) => {
        if (active) {
          setConversationId(session.conversation_id);
          setMessages(session.messages);
        }
      })
      .catch((caught) => { if (active) setError(messageOf(caught)); });
    return () => { active = false; };
  }, [begin]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(event: FormEvent) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || !sessionId || busy) return;
    setBusy(true);
    setError("");
    setDraft("");
    try {
      const result = await api<{ candidate_message: Message; assistant_message: Message }>(
        `/api/guest/sessions/${sessionId}/messages`,
        { method: "POST", body: jsonBody({ content }) },
      );
      setMessages((current) => [...current, result.candidate_message, result.assistant_message]);
    } catch (caught) {
      setDraft(content);
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="guest-page" id="main-content">
      <a className="skip-link" href="#guest-chat">Skip to conversation</a>
      <header className="guest-header">
        <a className="brand-lockup" href="/"><span className="brand-mark">S</span><span>SmartCampus <b>AI</b></span></a>
        <Button variant="soft" onClick={onCreateAccount}>Create an account</Button>
      </header>
      <div className="guest-content">
        <section className="guest-intro">
          <Badge color="blue" variant="soft">No account needed to begin</Badge>
          <Heading size="7">Start with a question.</Heading>
          <Text as="p" size="3" color="gray">Explore your interests and ask about study options. You can create an account later to keep this conversation.</Text>
        </section>
        <section className="guest-chat chat-panel" id="guest-chat">
          <div className="panel-heading"><div><Heading size="4">Orientation conversation</Heading><Text size="2" color="gray">French, Tunisian Arabic, or Arabizi</Text></div><Badge color="gray" variant="soft">Guest session</Badge></div>
          <div className="chat-messages" aria-live="polite">
            {messages.length === 0 && <div className="chat-welcome"><span className="welcome-monogram">S</span><Heading size="4">What would you like to study?</Heading><Text size="2" color="gray">Tell me what subjects you enjoy or ask about the programmes listed in the source material.</Text></div>}
            {messages.map((message) => <article key={message.id} className={`chat-message ${message.sender}`}><Text size="1" weight="bold">{message.sender === "assistant" ? "SmartCampus guide" : "You"}</Text><Text as="p" size="2">{message.content}</Text>{message.citations?.length > 0 && <div className="citation-list"><Text size="1" weight="bold" color="gray">Sources used</Text>{message.citations.map((citation, index) => <span className="citation" key={`${message.id}-${index}`}>{citation.source_url ? <a href={citation.source_url} target="_blank" rel="noreferrer">{citation.title}</a> : citation.title} / {citation.institution}{citation.is_sample ? " / sample, not official" : ""}</span>)}</div>}</article>)}
            {busy && <div className="typing-state"><Spinner size="1" /><Text size="2" color="gray">Preparing a source-based reply…</Text></div>}
            <div ref={bottomRef} />
          </div>
          <form className="chat-composer" onSubmit={send}>
            <TextArea aria-label="Write your question" placeholder="Write a question or describe what matters to you…" value={draft} onChange={(event) => setDraft(event.target.value)} rows={2} maxLength={5000} />
            <div className="composer-actions"><Text size="1" color="gray">Guest sessions expire after 30 days.</Text><Button type="submit" disabled={!draft.trim() || busy || !conversationId}>{busy ? "Sending…" : "Send question"}</Button></div>
            {error && <p className="inline-error" role="alert">{error}</p>}
          </form>
        </section>
        <Text size="1" color="gray">Suggestions are exploratory, not admission advice. Do not share passwords or sensitive personal information.</Text>
      </div>
    </main>
  );
}

function ProfileForm({
  profile,
  onSave,
}: {
  profile: Profile;
  onSave: (value: Partial<Profile>) => Promise<void>;
}) {
  const [draft, setDraft] = useState<Profile>(profile);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    setDraft(profile);
  }, [profile]);
  function toggleInterest(value: string, checked: boolean) {
    setDraft((current) => ({
      ...current,
      interests: checked
        ? [...new Set([...current.interests, value])]
        : current.interests.filter((interest) => interest !== value),
    }));
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await onSave(draft);
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setSaving(false);
    }
  }
  return (
    <form className="stack-form" onSubmit={submit}>
      <div className="form-grid">
        <Field label="Preferred conversation language" id="profile-language">
          <Select.Root value={draft.preferred_language} onValueChange={(preferred_language) => setDraft({ ...draft, preferred_language })}>
            <Select.Trigger id="profile-language" />
            <Select.Content>
              <Select.Item value="fr">French</Select.Item>
              <Select.Item value="Tunisian Arabic / Arabic script">Tunisian Arabic</Select.Item>
              <Select.Item value="Arabizi">Arabizi</Select.Item>
            </Select.Content>
          </Select.Root>
        </Field>
        <Field label="Current study level" id="profile-level">
          <TextField.Root id="profile-level" value={draft.current_level} onChange={(event) => setDraft({ ...draft, current_level: event.target.value })} placeholder="For example, final year of secondary school" />
        </Field>
      </div>
      <fieldset className="interest-fieldset">
        <legend className="field-label">Subjects you enjoy</legend>
        <div className="interest-list">
          {interestOptions.map((interest) => (
            <label className="interest-option" key={interest}>
              <Checkbox checked={draft.interests.includes(interest)} onCheckedChange={(checked) => toggleInterest(interest, checked === true)} />
              <Text size="2">{interest}</Text>
            </label>
          ))}
        </div>
      </fieldset>
      <Field label="Goals and interests" id="profile-goals" hint="Only share information you are comfortable discussing with an adviser.">
        <TextArea id="profile-goals" value={draft.goals} onChange={(event) => setDraft({ ...draft, goals: event.target.value })} rows={3} />
      </Field>
      <Field label="Constraints or questions" id="profile-constraints">
        <TextArea id="profile-constraints" value={draft.constraints} onChange={(event) => setDraft({ ...draft, constraints: event.target.value })} rows={2} />
      </Field>
      {error && <p className="inline-error" role="alert">{error}</p>}
      <Button type="submit" variant="soft" disabled={saving}>{saving ? "Saving…" : "Save profile"}</Button>
    </form>
  );
}

function ProgramList({
  programs,
  onSelect,
  actionLabel = "View programme",
}: {
  programs: Program[];
  onSelect: (program: Program) => void;
  actionLabel?: string;
}) {
  if (!programs.length) return <div className="empty-state"><Heading size="4">No programmes available</Heading><Text color="gray">Ask an administrator to add verified programme information.</Text></div>;
  return (
    <div className="programme-grid">
      {programs.map((program) => (
        <Card className="programme-card" key={program.id}>
          <Flex justify="between" align="center" gap="2">
            <Badge color={program.institution === "IIT" ? "blue" : "green"} variant="soft">{program.institution}</Badge>
            {program.is_sample && <Badge color="amber" variant="soft">Sample</Badge>}
          </Flex>
          <Heading size="4">{program.title}</Heading>
          <Text size="2" color="gray">{program.level}{program.duration ? ` / ${program.duration}` : ""}</Text>
          <Text size="2" className="programme-summary">{program.summary}</Text>
          {program.subjects.length > 0 && (
            <Flex gap="2" wrap="wrap">{program.subjects.map((subject) => <Badge key={subject} color="gray" variant="outline">{subject}</Badge>)}</Flex>
          )}
          {program.source_url && <a className="source-link" href={program.source_url} target="_blank" rel="noreferrer">Open programme source</a>}
          <Button variant="soft" onClick={() => onSelect(program)}>{actionLabel}</Button>
        </Card>
      ))}
    </div>
  );
}

function ChatView({
  programs,
  profile,
  onRefreshProfile,
  onEditProfile,
}: {
  programs: Program[];
  profile: Profile;
  onRefreshProfile: () => Promise<void>;
  onEditProfile: () => void;
}) {
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [audioBusy, setAudioBusy] = useState(false);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [recommendationNote, setRecommendationNote] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void api<Array<{ id: number; messages: Message[] }>>("/api/conversations")
      .then((items) => {
        if (items.length) {
          setConversationId(items[0].id);
          setMessages(items[0].messages);
        }
      })
      .catch((caught) => setError(messageOf(caught)));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function startConversation() {
    const response = await api<{ id: number }>("/api/conversations", {
      method: "POST",
      body: jsonBody({ language: profile.preferred_language || "fr" }),
    });
    setConversationId(response.id);
    setMessages([]);
    return response.id;
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || busy) return;
    setBusy(true);
    setError("");
    setDraft("");
    try {
      let id = conversationId;
      if (!id) id = await startConversation();
      const result = await api<{ candidate_message: Message; assistant_message: Message; detected_language: string }>(
        `/api/conversations/${id}/messages`,
        { method: "POST", body: jsonBody({ content }) },
      );
      setMessages((current) => [...current, result.candidate_message, result.assistant_message]);
      await onRefreshProfile();
    } catch (caught) {
      setDraft(content);
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  async function transcribe(file: File | undefined) {
    if (!file) return;
    setAudioBusy(true);
    setError("");
    try {
      const data = new FormData();
      data.append("audio", file);
      const result = await api<{ text: string }>("/api/audio/transcribe", { method: "POST", body: data });
      setDraft((current) => `${current}${current ? " " : ""}${result.text}`);
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setAudioBusy(false);
    }
  }

  async function recommend() {
    setBusy(true);
    setError("");
    try {
      const result = await api<{ recommendations: Recommendation[]; disclaimer: string }>("/api/recommendations", { method: "POST" });
      setRecommendations(result.recommendations);
      setRecommendationNote(result.disclaimer);
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="workspace-grid conversation-layout">
      <section className="chat-panel">
        <div className="panel-heading">
          <div><Heading size="5">Talk through your options</Heading><Text size="2" color="gray">Ask in French, Tunisian Arabic, or Arabizi.</Text></div>
          <Badge color="gray" variant="soft">{profile.preferred_language || "French"}</Badge>
        </div>
        <div className="chat-messages" aria-live="polite">
          {messages.length === 0 && (
            <div className="chat-welcome">
              <span className="welcome-monogram">S</span>
              <Heading size="4">What would you like to study?</Heading>
              <Text size="2" color="gray">Tell me what subjects you enjoy or what you are unsure about. I’ll help you prepare questions for an adviser.</Text>
              <Flex gap="2" wrap="wrap">
                {["I enjoy maths and computing", "What study paths are listed?", "I have questions about admissions"].map((suggestion) => (
                  <button className="suggestion" key={suggestion} type="button" onClick={() => setDraft(suggestion)}>{suggestion}</button>
                ))}
              </Flex>
            </div>
          )}
          {messages.map((message) => (
            <article key={message.id} className={`chat-message ${message.sender}`}>
              <Text size="1" weight="bold">{message.sender === "assistant" ? "SmartCampus guide" : "You"}</Text>
              <Text as="p" size="2">{message.content}</Text>
              {message.citations?.length > 0 && (
                <div className="citation-list">
                  <Text size="1" weight="bold" color="gray">Sources used</Text>
                  {message.citations.map((citation, index) => (
                    <span className="citation" key={`${message.id}-${index}`}>
                      {citation.source_url ? <a href={citation.source_url} target="_blank" rel="noreferrer">{citation.title}</a> : citation.title}
                      {" / "}{citation.institution}{citation.is_sample ? " / sample, not official" : ""}
                    </span>
                  ))}
                </div>
              )}
            </article>
          ))}
          {busy && <div className="typing-state"><Spinner size="1" /><Text size="2" color="gray">Preparing a source-based reply…</Text></div>}
          <div ref={bottomRef} />
        </div>
        <form className="chat-composer" onSubmit={send}>
          <TextArea aria-label="Write your question" placeholder="Write a question or describe what matters to you…" value={draft} onChange={(event) => setDraft(event.target.value)} rows={2} maxLength={5000} />
          <div className="composer-actions">
            <label className="file-action">
              <input aria-label="Transcribe a voice note" type="file" accept=".webm,.wav,.mp3,.m4a,.mp4,.ogg,.mpeg,audio/*" onChange={(event) => { void transcribe(event.target.files?.[0]); event.currentTarget.value = ""; }} />
              {audioBusy ? "Transcribing…" : "Add a voice note"}
            </label>
            <Button type="submit" disabled={!draft.trim() || busy}>Send question</Button>
          </div>
          {error && <p className="inline-error" role="alert">{error}</p>}
          <Text size="1" color="gray">Voice transcription requires a configured speech provider. Do not share passwords or sensitive personal information.</Text>
        </form>
      </section>

      <aside className="orientation-aside">
        <Card className="aside-card">
          <Text size="1" weight="bold" color="gray">YOUR ORIENTATION PROFILE</Text>
          <Heading size="4">What matters to you</Heading>
          <div className="profile-summary">
            <Text size="2"><b>Study level</b><br />{profile.current_level || "Not shared yet"}</Text>
            <Text size="2"><b>Interests</b><br />{profile.interests.length ? profile.interests.join(", ") : "Add a few subjects to begin"}</Text>
            <Text size="2"><b>Goal</b><br />{profile.goals || "Still to explore"}</Text>
          </div>
          <Button variant="soft" onClick={onEditProfile}>Edit my profile</Button>
        </Card>
        <Card className="aside-card">
          <Flex justify="between" align="center" gap="3">
            <div><Heading size="4">Explore a shortlist</Heading><Text size="2" color="gray">Based on interests you have shared.</Text></div>
            <Button variant="soft" onClick={recommend} disabled={busy}>Compare</Button>
          </Flex>
          {recommendationNote && <Text as="p" size="1" color="gray">{recommendationNote}</Text>}
          {recommendations.map((item) => (
            <div className="recommendation-row" key={item.program.id}>
              <div><Text size="2" weight="bold">{item.program.title}</Text><Text as="p" size="1" color="gray">{item.explanation}</Text></div>
              <Badge color="blue" variant="soft">{item.interest_overlap}% overlap</Badge>
            </div>
          ))}
        </Card>
        <Text size="1" color="gray">Orientation suggestions are exploratory. They are not an eligibility check or admission decision. An academic adviser reviews recommendations.</Text>
      </aside>
      <section className="profile-editor" id="profile-editor">
        <div><Heading size="4">Your profile</Heading><Text size="2" color="gray">You can edit or remove these details at any time.</Text></div>
        <ProfileForm profile={profile} onSave={async (value) => { await api("/api/profile", { method: "PUT", body: jsonBody(value) }); await onRefreshProfile(); }} />
      </section>
      {programs.length === 0 && <Text size="1" color="gray">Ask an administrator to add programme sources before relying on catalogue answers.</Text>}
    </div>
  );
}

function CandidateJourney({
  programs,
  registrations,
  appointments,
  notifications,
  onRefresh,
  onToast,
}: {
  programs: Program[];
  registrations: Registration[];
  appointments: Appointment[];
  notifications: { id: number; subject: string; delivery_status: string; error: string; created_at: string }[];
  onRefresh: () => Promise<void>;
  onToast: (message: string) => void;
}) {
  const [selectedProgram, setSelectedProgram] = useState<number | "">("");
  const [consent, setConsent] = useState(false);
  const [notes, setNotes] = useState("");
  const [questionnaire, setQuestionnaire] = useState<Questionnaire | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function register(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api("/api/preregistrations", { method: "POST", body: jsonBody({ program_id: selectedProgram, consent, notes }) });
      setConsent(false);
      setNotes("");
      await onRefresh();
      onToast("Pre-registration submitted for adviser review.");
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  async function startQuiz(programId: number) {
    setError("");
    setBusy(true);
    try {
      const quiz = await api<Questionnaire>(`/api/quizzes?program_id=${programId}`, { method: "POST" });
      setQuestionnaire(quiz);
      setAnswers({});
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  async function submitQuiz(event: FormEvent) {
    event.preventDefault();
    if (!questionnaire) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ completion_score: number; summary: string }>(
        `/api/quizzes/${questionnaire.id}/submit`,
        { method: "POST", body: jsonBody({ answers }) },
      );
      onToast(`Questionnaire shared with the interview team. ${result.completion_score}% of questions answered.`);
      setQuestionnaire(null);
      await onRefresh();
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  async function appointmentResponse(id: number, action: "confirm" | "decline") {
    setError("");
    try {
      await api(`/api/appointments/${id}?action=${action}`, { method: "PATCH" });
      await onRefresh();
    } catch (caught) {
      setError(messageOf(caught));
    }
  }

  return (
    <div className="journey-layout">
      <div className="journey-main">
        <section className="journey-section">
          <div className="section-title"><div><Heading size="5">Pre-registration</Heading><Text size="2" color="gray">Share a programme choice with the academic team.</Text></div><Badge color="gray" variant="soft">Human review</Badge></div>
          <form className="stack-form" onSubmit={register}>
            <Field label="Programme" id="registration-programme">
              <Select.Root value={selectedProgram ? String(selectedProgram) : ""} onValueChange={(value) => setSelectedProgram(Number(value))}>
                <Select.Trigger id="registration-programme" placeholder="Choose a programme" />
                <Select.Content>{programs.map((program) => <Select.Item key={program.id} value={String(program.id)}>{program.institution} / {program.title}{program.is_sample ? " / sample" : ""}</Select.Item>)}</Select.Content>
              </Select.Root>
            </Field>
            <Field label="Anything else you would like the adviser to know?" id="registration-notes">
              <TextArea id="registration-notes" value={notes} onChange={(event) => setNotes(event.target.value)} rows={3} maxLength={2000} />
            </Field>
            <label className="consent-row">
              <Checkbox checked={consent} onCheckedChange={(checked) => setConsent(checked === true)} />
              <Text size="2">I agree to share my account and orientation details with the relevant admissions team so they can review this pre-registration request.</Text>
            </label>
            {error && <p className="inline-error" role="alert">{error}</p>}
            <Button type="submit" disabled={busy || !selectedProgram || !consent}>{busy ? "Submitting…" : "Submit for review"}</Button>
            <Text size="1" color="gray">Submitting a request does not confirm admission or reserve a place.</Text>
          </form>
        </section>

        <section className="journey-section">
          <div className="section-title"><div><Heading size="5">Your requests</Heading><Text size="2" color="gray">Academic teams review requests and record official updates.</Text></div></div>
          {registrations.length ? (
            <div className="journey-list">
              {registrations.map((registration) => (
                <article className="journey-row" key={registration.id}>
                  <div><Text weight="bold" size="2">{registration.program.title}</Text><Text as="p" size="1" color="gray">{registration.program.institution} / requested {dateLabel(registration.created_at)}</Text></div>
                  <StatusBadge value={registration.status} sample={registration.program.is_sample} />
                  <Button size="1" variant="soft" onClick={() => void startQuiz(registration.program.id)} disabled={busy}>Prepare for interview</Button>
                </article>
              ))}
            </div>
          ) : <div className="empty-state"><Text weight="bold">No pre-registration requests yet</Text><Text size="2" color="gray">When you are ready, choose a programme above to start.</Text></div>}
        </section>

        {questionnaire && (
          <section className="journey-section quiz-section">
            <div className="section-title"><div><Heading size="5">Interview preparation</Heading><Text size="2" color="gray">{questionnaire.program.title}</Text></div><Badge color="amber" variant="soft">Exploratory</Badge></div>
            <Text size="2" color="gray">This questionnaire helps an adviser prepare. It is not a scored admission test.</Text>
            <form className="stack-form" onSubmit={submitQuiz}>
              {questionnaire.questions.map((question) => (
                <fieldset className="quiz-question" key={question.id}>
                  <legend className="field-label">{question.question}</legend>
                  {question.type === "multi" && (question.options ?? []).map((option) => (
                    <label className="quiz-option" key={option}>
                      <Checkbox
                        checked={Array.isArray(answers[question.id]) && (answers[question.id] as string[]).includes(option)}
                        onCheckedChange={(checked) => {
                          const current = Array.isArray(answers[question.id]) ? answers[question.id] as string[] : [];
                          setAnswers({ ...answers, [question.id]: checked ? [...current, option] : current.filter((value) => value !== option) });
                        }}
                      />
                      <Text size="2">{option}</Text>
                    </label>
                  ))}
                  {question.type === "single" && (question.options ?? []).map((option) => (
                    <label className="quiz-option" key={option}>
                      <input type="radio" name={question.id} checked={answers[question.id] === option} onChange={() => setAnswers({ ...answers, [question.id]: option })} />
                      <Text size="2">{option}</Text>
                    </label>
                  ))}
                  {question.type === "text" && <TextArea aria-label={question.question} rows={2} value={String(answers[question.id] ?? "")} onChange={(event) => setAnswers({ ...answers, [question.id]: event.target.value })} />}
                </fieldset>
              ))}
              {error && <p className="inline-error" role="alert">{error}</p>}
              <Flex gap="2"><Button type="submit" disabled={busy}>{busy ? "Sending…" : "Share with interview team"}</Button><Button type="button" variant="soft" onClick={() => setQuestionnaire(null)}>Close</Button></Flex>
            </form>
          </section>
        )}
      </div>

      <aside className="journey-aside">
        <Card className="aside-card">
          <Heading size="4">Interview times</Heading>
          <Text size="2" color="gray">Times are proposed by a coordinator. Confirm one to add it to your journey.</Text>
          {appointments.length ? appointments.map((appointment) => (
            <div className="appointment-item" key={appointment.id}>
              <Text weight="bold" size="2">{dateLabel(appointment.starts_at)}</Text>
              <Text size="1" color="gray">{appointment.duration_minutes} minutes / {appointment.mode === "online" ? "Online" : appointment.location || "On campus"}</Text>
              <StatusBadge value={appointment.status} />
              {appointment.status === "proposed" && (
                <Flex gap="2">
                  <Button size="1" onClick={() => void appointmentResponse(appointment.id, "confirm")}>Confirm</Button>
                  <Button size="1" variant="soft" color="gray" onClick={() => void appointmentResponse(appointment.id, "decline")}>Decline</Button>
                </Flex>
              )}
            </div>
          )) : <div className="empty-state"><Text size="2" color="gray">No interview time has been proposed.</Text></div>}
        </Card>
        <Card className="aside-card">
          <Heading size="4">Updates</Heading>
          {notifications.length ? notifications.slice(0, 5).map((notification) => (
            <div className="notification-item" key={notification.id}>
              <Text size="2" weight="bold">{notification.subject}</Text>
              <Text size="1" color="gray">{statusNames[notification.delivery_status] ?? notification.delivery_status} / {dateLabel(notification.created_at)}</Text>
              {notification.delivery_status !== "sent" && <Text size="1" color="amber">{notification.error || "Email sending is not configured. This update is available here."}</Text>}
            </div>
          )) : <Text size="2" color="gray">Updates about your request will appear here.</Text>}
        </Card>
      </aside>
    </div>
  );
}

function CatalogManager({
  programs,
  onRefresh,
  canEdit,
}: {
  programs: Program[];
  onRefresh: () => Promise<void>;
  canEdit: boolean;
}) {
  const blank = {
    code: "",
    institution: "IIT" as "IIT" | "ISB",
    title: "",
    level: "",
    summary: "",
    duration: "",
    prerequisites: "",
    tuition: "",
    subjects: "",
    careers: "",
    source_url: "",
    is_sample: false,
    is_active: true,
  };
  const [draft, setDraft] = useState(blank);
  const [editing, setEditing] = useState<number | null>(null);
  const [viewing, setViewing] = useState<Program | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function startEdit(program: Program) {
    setEditing(program.id);
    setDraft({ ...program, subjects: program.subjects.join(", "), careers: program.careers.join(", "), source_url: program.source_url ?? "" });
  }
  function reset() { setEditing(null); setDraft(blank); }
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const payload = {
      ...draft,
      subjects: draft.subjects.split(",").map((item) => item.trim()).filter(Boolean),
      careers: draft.careers.split(",").map((item) => item.trim()).filter(Boolean),
      source_url: draft.source_url || null,
    };
    try {
      await api(editing ? `/api/programs/${editing}` : "/api/programs", {
        method: editing ? "PUT" : "POST",
        body: jsonBody(payload),
      });
      await onRefresh();
      reset();
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="catalog-layout">
      <section className="journey-section">
        <div className="section-title"><div><Heading size="5">Programme catalogue</Heading><Text size="2" color="gray">Only verified records should be used for candidate guidance.</Text></div><Badge color="amber" variant="soft">{programs.filter((program) => program.is_sample).length} sample records</Badge></div>
        <ProgramList
          programs={programs}
          onSelect={canEdit ? startEdit : setViewing}
          actionLabel={canEdit ? "Edit programme" : "View programme"}
        />
      </section>
      {canEdit && (
        <aside className="journey-section">
          <div className="section-title"><Heading size="4">{editing ? "Edit programme" : "Add a programme"}</Heading>{editing && <Button size="1" variant="soft" onClick={reset}>Cancel</Button>}</div>
          <form className="stack-form" onSubmit={submit}>
            <div className="form-grid">
              <Field label="Programme code" id="catalog-code"><TextField.Root id="catalog-code" required value={draft.code} onChange={(event) => setDraft({ ...draft, code: event.target.value })} /></Field>
              <Field label="Institution" id="catalog-institution">
                <Select.Root value={draft.institution} onValueChange={(institution: "IIT" | "ISB") => setDraft({ ...draft, institution })}><Select.Trigger id="catalog-institution" /><Select.Content><Select.Item value="IIT">IIT</Select.Item><Select.Item value="ISB">ISB</Select.Item></Select.Content></Select.Root>
              </Field>
            </div>
            <Field label="Programme title" id="catalog-title"><TextField.Root id="catalog-title" required value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></Field>
            <div className="form-grid">
              <Field label="Level" id="catalog-level"><TextField.Root id="catalog-level" required value={draft.level} onChange={(event) => setDraft({ ...draft, level: event.target.value })} /></Field>
              <Field label="Duration" id="catalog-duration"><TextField.Root id="catalog-duration" value={draft.duration} onChange={(event) => setDraft({ ...draft, duration: event.target.value })} /></Field>
            </div>
            <Field label="Verified summary" id="catalog-summary"><TextArea id="catalog-summary" value={draft.summary} onChange={(event) => setDraft({ ...draft, summary: event.target.value })} rows={4} /></Field>
            <Field label="Prerequisites" id="catalog-prerequisites"><TextArea id="catalog-prerequisites" value={draft.prerequisites} onChange={(event) => setDraft({ ...draft, prerequisites: event.target.value })} rows={2} /></Field>
            <Field label="Verified tuition and fee information" id="catalog-tuition" hint="Leave blank until an official amount and source are available."><TextArea id="catalog-tuition" value={draft.tuition} onChange={(event) => setDraft({ ...draft, tuition: event.target.value })} rows={2} /></Field>
            <Field label="Subjects, separated by commas" id="catalog-subjects"><TextField.Root id="catalog-subjects" value={draft.subjects} onChange={(event) => setDraft({ ...draft, subjects: event.target.value })} /></Field>
            <Field label="Career outcomes, separated by commas" id="catalog-careers"><TextField.Root id="catalog-careers" value={draft.careers} onChange={(event) => setDraft({ ...draft, careers: event.target.value })} /></Field>
            <Field label="Official source URL" id="catalog-source"><TextField.Root id="catalog-source" type="url" value={draft.source_url} onChange={(event) => setDraft({ ...draft, source_url: event.target.value })} /></Field>
            <label className="consent-row"><Checkbox checked={draft.is_sample} onCheckedChange={(checked) => setDraft({ ...draft, is_sample: checked === true })} /><Text size="2">This is demonstration data, not official information.</Text></label>
            <label className="consent-row"><Checkbox checked={draft.is_active} onCheckedChange={(checked) => setDraft({ ...draft, is_active: checked === true })} /><Text size="2">Visible to candidates</Text></label>
            {error && <p className="inline-error" role="alert">{error}</p>}
            <Button type="submit" disabled={busy}>{busy ? "Saving…" : editing ? "Save changes" : "Add programme"}</Button>
          </form>
        </aside>
      )}
      {!canEdit && (
        <Dialog.Root open={Boolean(viewing)} onOpenChange={(open) => { if (!open) setViewing(null); }}>
          <Dialog.Content maxWidth="520px">
            <Dialog.Title>{viewing?.title}</Dialog.Title>
            <Flex gap="2" wrap="wrap">
              <Badge color={viewing?.institution === "IIT" ? "blue" : "green"} variant="soft">{viewing?.institution}</Badge>
              {viewing?.is_sample && <Badge color="amber" variant="soft">Sample, not official</Badge>}
            </Flex>
            <Text as="p" size="2">{viewing?.summary}</Text>
            <Separator size="4" />
            <Text as="p" size="2"><b>Level:</b> {viewing?.level || "Not provided"}</Text>
            <Text as="p" size="2"><b>Duration:</b> {viewing?.duration || "Not provided"}</Text>
            <Text as="p" size="2"><b>Prerequisites:</b> {viewing?.prerequisites || "Not provided"}</Text>
            <Text as="p" size="2"><b>Tuition:</b> {viewing?.tuition || "Not provided"}</Text>
            <Text as="p" size="2"><b>Subjects:</b> {viewing?.subjects.join(", ") || "Not provided"}</Text>
            <Text as="p" size="2"><b>Career outcomes:</b> {viewing?.careers.join(", ") || "Not provided"}</Text>
            {viewing?.source_url && <a className="source-link" href={viewing.source_url} target="_blank" rel="noreferrer">Open programme source</a>}
            <Dialog.Close><Button variant="soft">Close</Button></Dialog.Close>
          </Dialog.Content>
        </Dialog.Root>
      )}
    </div>
  );
}

function KnowledgeManager() {
  const [documents, setDocuments] = useState<Array<{ id: number; title: string; institution: string; is_sample: boolean; updated_at: string }>>([]);
  const [draft, setDraft] = useState({ title: "", institution: "IIT", content: "", source_url: "", is_sample: false });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loadingDocuments, setLoadingDocuments] = useState(true);
  const [loadError, setLoadError] = useState("");
  const load = useCallback(async () => {
    setLoadingDocuments(true);
    setLoadError("");
    try {
      setDocuments(await api("/api/admin/documents"));
    } finally {
      setLoadingDocuments(false);
    }
  }, []);
  useEffect(() => { void load().catch((caught) => setLoadError(messageOf(caught))); }, [load]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/api/admin/documents", { method: "POST", body: jsonBody({ ...draft, source_url: draft.source_url || null }) });
      setDraft({ title: "", institution: "IIT", content: "", source_url: "", is_sample: false });
      await load();
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="catalog-layout">
      <section className="journey-section">
        <Heading size="5">Knowledge sources</Heading>
        <Text size="2" color="gray">Only administrator-approved, verified source content should support factual answers.</Text>
        {loadingDocuments ? (
          <Text as="p" size="2" color="gray" role="status">Loading indexed sources…</Text>
        ) : loadError ? (
          <div className="load-error" role="alert">
            <Text size="2">{loadError}</Text>
            <Button size="1" variant="soft" onClick={() => void load().catch((caught) => setLoadError(messageOf(caught)))}>Retry</Button>
          </div>
        ) : documents.length ? documents.map((document) => (
          <div className="document-row" key={document.id}>
            <div><Text weight="bold" size="2">{document.title}</Text><Text as="p" size="1" color="gray">{document.institution} / updated {dateLabel(document.updated_at)}</Text></div>
            {document.is_sample && <Badge color="amber" variant="soft">Sample</Badge>}
          </div>
        )) : <div className="empty-state"><Text size="2">No indexed sources yet.</Text></div>}
        <Text size="1" color="gray">The retrieval index uses pgvector when PostgreSQL is configured, and local vector similarity for a SQLite demo database.</Text>
      </section>
      <aside className="journey-section">
        <Heading size="4">Add a source</Heading>
        <form className="stack-form" onSubmit={submit}>
          <Field label="Source title" id="doc-title"><TextField.Root id="doc-title" required value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></Field>
          <Field label="Institution" id="doc-institution"><Select.Root value={draft.institution} onValueChange={(institution) => setDraft({ ...draft, institution })}><Select.Trigger id="doc-institution" /><Select.Content><Select.Item value="IIT">IIT</Select.Item><Select.Item value="ISB">ISB</Select.Item></Select.Content></Select.Root></Field>
          <Field label="Verified source text" id="doc-content"><TextArea id="doc-content" required minLength={40} value={draft.content} onChange={(event) => setDraft({ ...draft, content: event.target.value })} rows={8} /></Field>
          <Field label="Official source URL" id="doc-url"><TextField.Root id="doc-url" type="url" value={draft.source_url} onChange={(event) => setDraft({ ...draft, source_url: event.target.value })} /></Field>
          <label className="consent-row"><Checkbox checked={draft.is_sample} onCheckedChange={(checked) => setDraft({ ...draft, is_sample: checked === true })} /><Text size="2">This document contains demonstration content.</Text></label>
          {error && <p className="inline-error" role="alert">{error}</p>}
          <Button type="submit" disabled={busy}>{busy ? "Indexing…" : "Index source"}</Button>
        </form>
      </aside>
    </div>
  );
}

function CandidateWorkspace({
  user,
  profile,
  programs,
  registrations,
  appointments,
  notifications,
  onRefresh,
  onToast,
  onEditProfile,
  view,
}: {
  user: User;
  profile: Profile;
  programs: Program[];
  registrations: Registration[];
  appointments: Appointment[];
  notifications: { id: number; subject: string; delivery_status: string; error: string; created_at: string }[];
  onRefresh: () => Promise<void>;
  onToast: (message: string) => void;
  onEditProfile: () => void;
  view: View;
}) {
  const [programDetail, setProgramDetail] = useState<Program | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [recommendationError, setRecommendationError] = useState("");
  async function getRecommendations() {
    setRecommendationError("");
    try {
      const result = await api<{ recommendations: Recommendation[] }>("/api/recommendations", { method: "POST" });
      setRecommendations(result.recommendations);
    } catch (error) {
      setRecommendationError(messageOf(error));
    }
  }
  if (view === "conversation") return <ChatView programs={programs} profile={profile} onRefreshProfile={onRefresh} onEditProfile={onEditProfile} />;
  if (view === "programmes") {
    return (
      <>
        <section className="page-intro"><div><Text size="2" color="gray">Catalogue</Text><Heading size="7">Explore your options</Heading><Text as="p" size="3" color="gray">Review listed programmes and check details with an adviser before you decide.</Text></div><Button variant="soft" onClick={getRecommendations}>Compare with my profile</Button></section>
        {recommendationError && <p className="inline-error" role="alert">{recommendationError}</p>}
        {recommendations.length > 0 && <div className="recommendation-banner"><Text size="2" weight="bold">Exploratory suggestions</Text><Text size="2" color="gray">Interest overlap only, not admissions eligibility. Sample entries are not official.</Text><div className="recommendation-list">{recommendations.map((item) => <div key={item.program.id}><b>{item.program.title}</b><span>{item.interest_overlap}% interest overlap</span><small>{item.explanation}</small></div>)}</div></div>}
        <ProgramList programs={programs} onSelect={setProgramDetail} />
        <Dialog.Root open={Boolean(programDetail)} onOpenChange={(open) => { if (!open) setProgramDetail(null); }}>
          <Dialog.Content maxWidth="520px">
            <Dialog.Title>{programDetail?.title}</Dialog.Title>
            <Flex gap="2"><Badge color="blue" variant="soft">{programDetail?.institution}</Badge>{programDetail?.is_sample && <Badge color="amber" variant="soft">Sample, not official</Badge>}</Flex>
            <Text as="p" size="2">{programDetail?.summary}</Text>
            <Separator size="4" />
            <Text as="p" size="2"><b>Level:</b> {programDetail?.level || "Not provided"}</Text>
            <Text as="p" size="2"><b>Duration:</b> {programDetail?.duration || "Not provided"}</Text>
            <Text as="p" size="2"><b>Prerequisites:</b> {programDetail?.prerequisites || "Not provided"}</Text>
            <Text as="p" size="2"><b>Tuition:</b> {programDetail?.tuition || "Not provided"}</Text>
            <Text as="p" size="2"><b>Subjects:</b> {programDetail?.subjects.join(", ") || "Not provided"}</Text>
            <Text as="p" size="2"><b>Career outcomes:</b> {programDetail?.careers.join(", ") || "Not provided"}</Text>
            {programDetail?.source_url && <a className="source-link" href={programDetail.source_url} target="_blank" rel="noreferrer">Open official source</a>}
            <Dialog.Close><Button variant="soft">Close</Button></Dialog.Close>
          </Dialog.Content>
        </Dialog.Root>
      </>
    );
  }
  if (view === "journey") {
    return <><section className="page-intro"><div><Text size="2" color="gray">Candidate workspace</Text><Heading size="7">Your next steps</Heading><Text as="p" size="3" color="gray">Manage pre-registration, interview preparation, and updates in one place.</Text></div></section><CandidateJourney programs={programs} registrations={registrations} appointments={appointments} notifications={notifications} onRefresh={onRefresh} onToast={onToast} /></>;
  }
  return (
    <div className="candidate-overview">
      <section className="welcome-banner">
        <div><Text size="2" color="gray">Your orientation workspace</Text><Heading size="7">Welcome, {user.name.split(" ")[0]}.</Heading><Text as="p" size="3" color="gray">Start with what interests you. The next steps can wait until you are ready.</Text><Flex gap="3" wrap="wrap"><Button onClick={() => window.dispatchEvent(new CustomEvent("smartcampus:navigate", { detail: "conversation" }))}>Talk through my options</Button><Button variant="soft" onClick={() => window.dispatchEvent(new CustomEvent("smartcampus:navigate", { detail: "programmes" }))}>Browse programmes</Button></Flex></div>
        <div className="welcome-side"><Text size="1" weight="bold" color="gray">YOUR PROGRESS</Text><div className="journey-progress"><span className={profile.interests.length ? "complete" : ""}>Profile</span><i /><span className={registrations.length ? "complete" : ""}>Request</span><i /><span className={appointments.some((appointment) => appointment.status === "confirmed") ? "complete" : ""}>Interview</span></div><Text size="1" color="gray">Your adviser confirms official academic decisions.</Text></div>
      </section>
      <div className="overview-lower">
        <section className="journey-section">
          <div className="section-title"><div><Heading size="5">A path that stays yours</Heading><Text size="2" color="gray">Take one step now or come back later.</Text></div></div>
          <div className="next-step-grid">
            <button className="next-step" onClick={() => window.dispatchEvent(new CustomEvent("smartcampus:navigate", { detail: "conversation" }))}><span className="step-number">01</span><b>Explore a direction</b><span>Talk about subjects, interests, and goals.</span></button>
            <button className="next-step" onClick={() => window.dispatchEvent(new CustomEvent("smartcampus:navigate", { detail: "programmes" }))}><span className="step-number">02</span><b>Compare programmes</b><span>See available options and source details.</span></button>
            <button className="next-step" onClick={() => window.dispatchEvent(new CustomEvent("smartcampus:navigate", { detail: "journey" }))}><span className="step-number">03</span><b>Prepare with an adviser</b><span>Pre-register when you are ready.</span></button>
          </div>
        </section>
        <aside className="journey-section">
          <Heading size="4">Your latest updates</Heading>
          {registrations.length ? registrations.slice(0, 2).map((item) => <div className="overview-update" key={item.id}><Text size="2" weight="bold">{item.program.title}</Text><StatusBadge value={item.status} sample={item.program.is_sample} /></div>) : <div className="empty-state"><Text size="2" color="gray">You have not sent a pre-registration request.</Text><Button variant="soft" onClick={() => window.dispatchEvent(new CustomEvent("smartcampus:navigate", { detail: "journey" }))}>Review next steps</Button></div>}
          {appointments.filter((appointment) => appointment.status === "proposed" || appointment.status === "confirmed").slice(0, 1).map((appointment) => <div className="overview-update" key={appointment.id}><Text size="2" weight="bold">Interview / {dateLabel(appointment.starts_at)}</Text><StatusBadge value={appointment.status} /></div>)}
        </aside>
      </div>
      <section className="profile-editor" id="profile-editor">
        <div><Heading size="4">Your orientation profile</Heading><Text size="2" color="gray">Share only what helps your conversation.</Text></div>
        <ProfileForm profile={profile} onSave={async (value) => { await api("/api/profile", { method: "PUT", body: jsonBody(value) }); await onRefresh(); }} />
      </section>
    </div>
  );
}

function StaffWorkspace({
  user,
  view,
  programs,
  candidates,
  registrations,
  stats,
  quizzes,
  appointments,
  onRefresh,
}: {
  user: User;
  view: View;
  programs: Program[];
  candidates: CandidateRecord[];
  registrations: Registration[];
  stats: Stats | null;
  quizzes: Questionnaire[];
  appointments: Appointment[];
  onRefresh: () => Promise<void>;
}) {
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateRecord | null>(null);
  const [reviewStatus, setReviewStatus] = useState("needs_information");
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewError, setReviewError] = useState("");
  const [conversations, setConversations] = useState<Array<{ id: number; messages: Message[] }>>([]);
  const [appointmentForm, setAppointmentForm] = useState({ starts_at: "", duration_minutes: "30", mode: "online", location: "", notes: "" });
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");

  async function selectCandidate(candidate: CandidateRecord) {
    setSelectedCandidate(candidate);
    setReviewError("");
    try {
      const result = await api<Array<{ id: number; messages: Message[] }>>(`/api/staff/conversations/${candidate.user.id}`);
      setConversations(result);
    } catch (caught) {
      setReviewError(messageOf(caught));
    }
  }

  async function review(registration: Registration) {
    setBusy(true);
    setReviewError("");
    try {
      await api(`/api/preregistrations/${registration.id}`, { method: "PATCH", body: jsonBody({ status: reviewStatus, notes: reviewNotes }) });
      await onRefresh();
    } catch (caught) {
      setReviewError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  async function proposeAppointment(event: FormEvent) {
    event.preventDefault();
    if (!selectedCandidate || !appointmentForm.starts_at) return;
    setBusy(true);
    setActionError("");
    try {
      await api("/api/appointments", {
        method: "POST",
        body: jsonBody({
          candidate_id: selectedCandidate.user.id,
          starts_at: new Date(appointmentForm.starts_at).toISOString(),
          duration_minutes: Number(appointmentForm.duration_minutes),
          mode: appointmentForm.mode,
          location: appointmentForm.location,
          notes: appointmentForm.notes,
        }),
      });
      setAppointmentForm({ starts_at: "", duration_minutes: "30", mode: "online", location: "", notes: "" });
      await onRefresh();
    } catch (caught) {
      setActionError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  if (view === "programmes") return <CatalogManager programs={programs} onRefresh={onRefresh} canEdit={user.role === "admin"} />;
  if (view === "knowledge") return user.role === "admin" ? <KnowledgeManager /> : <div className="journey-section"><Heading size="5">Knowledge sources</Heading><Text color="gray">Source documents are managed by the platform administrator.</Text></div>;
  if (view === "candidates") {
    return (
      <div className="staff-layout">
        <section className="journey-section candidate-table-section">
          <div className="section-title"><div><Heading size="5">Candidate applications</Heading><Text size="2" color="gray">Review profiles, source conversations, questionnaires, and requests.</Text></div><Badge color="gray" variant="soft">{candidates.length} candidates</Badge></div>
          {candidates.length ? (
            <Table.Root variant="surface">
              <Table.Header><Table.Row><Table.ColumnHeaderCell>Candidate</Table.ColumnHeaderCell><Table.ColumnHeaderCell>Interests</Table.ColumnHeaderCell><Table.ColumnHeaderCell>Request</Table.ColumnHeaderCell></Table.Row></Table.Header>
              <Table.Body>{candidates.map((candidate) => (
                <Table.Row key={candidate.user.id} className={selectedCandidate?.user.id === candidate.user.id ? "selected-row" : ""}>
                  <Table.Cell><button className="table-link" onClick={() => void selectCandidate(candidate)}>{candidate.user.name}<span>{candidate.user.email}</span></button></Table.Cell>
                  <Table.Cell>{candidate.profile?.interests?.join(", ") || "Not shared"}</Table.Cell>
                  <Table.Cell>{candidate.preregistrations.length ? <StatusBadge value={candidate.preregistrations[0].status} /> : "No request"}</Table.Cell>
                </Table.Row>
              ))}</Table.Body>
            </Table.Root>
          ) : <div className="empty-state"><Text weight="bold">No applications to review</Text><Text size="2" color="gray">Candidate records will appear here after they create an account or submit a request.</Text></div>}
        </section>
        {selectedCandidate && (
          <section className="journey-section candidate-detail">
            <div className="section-title"><div><Text size="1" color="gray">CANDIDATE SUMMARY</Text><Heading size="5">{selectedCandidate.user.name}</Heading><Text size="2" color="gray">{selectedCandidate.user.email}</Text></div><Button variant="soft" size="1" onClick={() => { setSelectedCandidate(null); setConversations([]); }}>Close</Button></div>
            <div className="profile-summary">
              <Text size="2"><b>Level</b><br />{selectedCandidate.profile?.current_level || "Not shared"}</Text>
              <Text size="2"><b>Interests</b><br />{selectedCandidate.profile?.interests?.join(", ") || "Not shared"}</Text>
              <Text size="2"><b>Goals</b><br />{selectedCandidate.profile?.goals || "Not shared"}</Text>
              <Text size="2"><b>Constraints</b><br />{selectedCandidate.profile?.constraints || "Not shared"}</Text>
            </div>
            {selectedCandidate.preregistrations.map((registration) => (
              <div className="review-block" key={registration.id}>
                <div><Text size="2" weight="bold">{registration.program.title}</Text><StatusBadge value={registration.status} sample={registration.program.is_sample} /></div>
                <Field label="Review status" id={`review-status-${registration.id}`}>
                  <Select.Root value={reviewStatus} onValueChange={setReviewStatus}><Select.Trigger id={`review-status-${registration.id}`} /><Select.Content><Select.Item value="needs_information">Request more information</Select.Item><Select.Item value="approved">Academic review complete</Select.Item><Select.Item value="rejected">Close request</Select.Item></Select.Content></Select.Root>
                </Field>
                <Field label="Notes for the candidate" id={`review-notes-${registration.id}`}><TextArea id={`review-notes-${registration.id}`} value={reviewNotes} onChange={(event) => setReviewNotes(event.target.value)} rows={2} /></Field>
                <Button size="2" onClick={() => void review(registration)} disabled={busy}>{busy ? "Saving…" : "Save human review"}</Button>
              </div>
            ))}
            {quizzes.filter((quiz) => quiz.candidate_id === selectedCandidate.user.id).map((quiz) => (
              <div className="review-block" key={quiz.id}>
                <Text size="2" weight="bold">Interview questionnaire / {quiz.program.title}</Text>
                <Text size="1" color="gray">{quiz.submitted_at ? `Answered ${dateLabel(quiz.submitted_at)}` : "Not yet submitted"} / completion only, not a knowledge or admission score</Text>
                <Text as="p" size="2">{quiz.summary || "Interview prompts available when the candidate completes the questionnaire."}</Text>
              </div>
            ))}
            <div className="review-block">
              <Text size="2" weight="bold">Conversation notes</Text>
              {conversations.length ? conversations.flatMap((conversation) => conversation.messages).slice(-8).map((message) => <div className={`conversation-snippet ${message.sender}`} key={message.id}><Text size="1" weight="bold">{message.sender === "assistant" ? "Guide" : "Candidate"}</Text><Text as="p" size="2">{message.content}</Text></div>) : <Text size="2" color="gray">No conversation history is available for this candidate.</Text>}
            </div>
            {user.role === "interviewer" || user.role === "admin" ? (
              <form className="review-block stack-form" onSubmit={proposeAppointment}>
                <Text size="2" weight="bold">Propose an interview time</Text>
                <Field label="Date and time" id="appointment-start"><TextField.Root id="appointment-start" type="datetime-local" required value={appointmentForm.starts_at} onChange={(event) => setAppointmentForm({ ...appointmentForm, starts_at: event.target.value })} /></Field>
                <Field label="Meeting format" id="appointment-mode"><Select.Root value={appointmentForm.mode} onValueChange={(mode) => setAppointmentForm({ ...appointmentForm, mode })}><Select.Trigger id="appointment-mode" /><Select.Content><Select.Item value="online">Online</Select.Item><Select.Item value="on_campus">On campus</Select.Item></Select.Content></Select.Root></Field>
                <Field label="Meeting link or location" id="appointment-location"><TextField.Root id="appointment-location" value={appointmentForm.location} onChange={(event) => setAppointmentForm({ ...appointmentForm, location: event.target.value })} /></Field>
                <Button type="submit" disabled={busy}>{busy ? "Sending…" : "Propose time"}</Button>
              </form>
            ) : null}
            {reviewError && <p className="inline-error" role="alert">{reviewError}</p>}
            {actionError && <p className="inline-error" role="alert">{actionError}</p>}
          </section>
        )}
      </div>
    );
  }
  if (view === "overview") {
    const metrics = stats ? [
      ["Candidate accounts", stats.candidates],
      ["Conversations", stats.conversations],
      ["Pre-registration requests", stats.preregistrations],
      ["Interview appointments", stats.appointments],
    ] as const : [];
    return (
      <div className="staff-overview">
        <section className="page-intro"><div><Text size="2" color="gray">{roleLabel(user.role)}</Text><Heading size="7">Admissions overview</Heading><Text as="p" size="3" color="gray">A live view of records in this workspace. Academic decisions remain with your team.</Text></div></section>
        <div className="metric-row">{metrics.map(([label, value]) => <Card className="metric-card" key={label}><Text size="2" color="gray">{label}</Text><Heading size="7">{value}</Heading></Card>)}</div>
        <div className="overview-lower">
          <section className="journey-section">
            <div className="section-title"><div><Heading size="5">Needs attention</Heading><Text size="2" color="gray">Requests awaiting a human review.</Text></div><Button variant="soft" onClick={() => window.dispatchEvent(new CustomEvent("smartcampus:navigate", { detail: "candidates" }))}>Open candidates</Button></div>
            {registrations.filter((registration) => registration.status === "pending_review" || registration.status === "needs_information").slice(0, 6).map((registration) => (
              <div className="document-row" key={registration.id}><div><Text weight="bold" size="2">{registration.program.title}</Text><Text as="p" size="1" color="gray">Candidate #{registration.candidate_id} / received {dateLabel(registration.created_at)}</Text></div><StatusBadge value={registration.status} sample={registration.program.is_sample} /></div>
            ))}
            {!registrations.some((registration) => registration.status === "pending_review" || registration.status === "needs_information") && <div className="empty-state"><Text size="2" color="gray">No requests are waiting for review.</Text></div>}
          </section>
          <section className="journey-section">
            <Heading size="5">Current pipeline</Heading>
            {Object.entries(stats?.registrations_by_status ?? {}).length ? Object.entries(stats?.registrations_by_status ?? {}).map(([status, count]) => <div className="pipeline-row" key={status}><Text size="2">{statusNames[status] ?? status}</Text><Badge color="blue" variant="soft">{count}</Badge></div>) : <div className="empty-state"><Text size="2" color="gray">Pipeline counts will appear when requests are submitted.</Text></div>}
            <Text size="1" color="gray">{stats?.data_note}</Text>
          </section>
        </div>
        {appointments.length > 0 && <section className="journey-section"><Heading size="5">Interview schedule</Heading>{appointments.slice(0, 6).map((appointment) => <div className="document-row" key={appointment.id}><div><Text weight="bold" size="2">Candidate #{appointment.user_id}</Text><Text as="p" size="1" color="gray">{dateLabel(appointment.starts_at)} / {appointment.mode}</Text></div><StatusBadge value={appointment.status} /></div>)}</section>}
      </div>
    );
  }
  return null;
}

function AppWorkspace() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [guestMode, setGuestMode] = useState(false);
  const [view, setView] = useState<View>("overview");
  const shouldFocusProfile = useRef(false);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [registrations, setRegistrations] = useState<Registration[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [notifications, setNotifications] = useState<Array<{ id: number; subject: string; delivery_status: string; error: string; created_at: string }>>([]);
  const [candidates, setCandidates] = useState<CandidateRecord[]>([]);
  const [quizzes, setQuizzes] = useState<Questionnaire[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [pageError, setPageError] = useState("");
  const [toast, setToast] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const isStaff = user !== null && user.role !== "candidate";

  const refresh = useCallback(async () => {
    if (!user) return;
    setRefreshing(true);
    setPageError("");
    try {
      const [programData, registrationData, appointmentData] = await Promise.all([
        api<Program[]>("/api/programs"),
        api<Registration[]>("/api/preregistrations"),
        api<Appointment[]>("/api/appointments"),
      ]);
      setPrograms(programData);
      setRegistrations(registrationData);
      setAppointments(appointmentData);
      if (user.role === "candidate") {
        const [profileData, notificationData] = await Promise.all([
          api<{ profile: Profile }>("/api/profile"),
          api<typeof notifications>("/api/notifications"),
        ]);
        setProfile(profileData.profile);
        setNotifications(notificationData);
      } else {
        const [statsData, candidateData, quizData] = await Promise.all([
          api<Stats>("/api/stats"),
          api<CandidateRecord[]>("/api/staff/candidates"),
          api<Questionnaire[]>("/api/quizzes"),
        ]);
        setStats(statsData);
        setCandidates(candidateData);
        setQuizzes(quizData);
      }
    } catch (caught) {
      setPageError(messageOf(caught));
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    let active = true;
    const token = sessionStorage.getItem("smartcampus_token");
    if (!token) {
      setGuestMode(
        Boolean(
          sessionStorage.getItem("smartcampus_guest_id") &&
            sessionStorage.getItem("smartcampus_guest_token"),
        ),
      );
      setLoading(false);
      return () => { active = false; };
    }
    void api<User>("/api/auth/me", {}, token)
      .then((authenticatedUser) => {
        if (active) setUser(authenticatedUser);
      })
      .catch(() => {
        sessionStorage.removeItem("smartcampus_token");
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (user) void refresh();
  }, [user, refresh]);

  useEffect(() => {
    if (view !== "overview" || !shouldFocusProfile.current) return;
    shouldFocusProfile.current = false;
    const frame = window.requestAnimationFrame(() => {
      document.getElementById("profile-editor")?.scrollIntoView({ behavior: "smooth" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [view]);

  useEffect(() => {
    function onNavigate(event: Event) {
      const requested = (event as CustomEvent<View>).detail;
      if (requested) setView(requested);
    }
    window.addEventListener("smartcampus:navigate", onNavigate);
    return () => window.removeEventListener("smartcampus:navigate", onNavigate);
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 5000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  function login(authenticatedUser: User, token: string) {
    sessionStorage.setItem("smartcampus_token", token);
    sessionStorage.removeItem("smartcampus_guest_token");
    sessionStorage.removeItem("smartcampus_guest_id");
    setGuestMode(false);
    setUser(authenticatedUser);
    setView("overview");
    setLoading(true);
  }

  function logout() {
    sessionStorage.removeItem("smartcampus_token");
    setUser(null);
    setPrograms([]);
    setRegistrations([]);
    setAppointments([]);
    setView("overview");
    setLoading(false);
  }

  function startGuest() {
    sessionStorage.removeItem("smartcampus_guest_id");
    sessionStorage.removeItem("smartcampus_guest_token");
    setGuestMode(true);
  }

  const nav: { id: View; label: string }[] = useMemo(() => {
    if (!user) return [];
    if (user.role === "candidate") return [
      { id: "overview", label: "Overview" },
      { id: "conversation", label: "Orientation chat" },
      { id: "programmes", label: "Programmes" },
      { id: "journey", label: "My journey" },
    ];
    const items: { id: View; label: string }[] = [
      { id: "overview", label: "Overview" },
      { id: "candidates", label: "Candidates" },
      { id: "programmes", label: "Programmes" },
    ];
    if (user.role === "admin") items.push({ id: "knowledge", label: "Knowledge sources" });
    return items;
  }, [user]);

  if (loading) {
    return <main className="loading-page"><Spinner size="3" /><Text size="2" color="gray">Loading your workspace…</Text></main>;
  }
  if (!user && guestMode) return <GuestChat onCreateAccount={() => setGuestMode(false)} />;
  if (!user) return <AuthScreen onLogin={login} onStartGuest={startGuest} onBackToGuest={() => setGuestMode(true)} hasGuestConversation={Boolean(sessionStorage.getItem("smartcampus_guest_id"))} />;

  return (
    <main className="app-shell" id="main-content">
      <a className="skip-link" href="#page-content">Skip to content</a>
      <header className="topbar">
        <a className="brand-lockup" href="/" aria-label="SmartCampus AI home">
          <span className="brand-mark">S</span><span>SmartCampus <b>AI</b></span>
        </a>
        <nav className="main-nav" aria-label="Main navigation">
          {nav.map((item) => <button key={item.id} className={`nav-item ${view === item.id ? "active" : ""}`} aria-current={view === item.id ? "page" : undefined} onClick={() => setView(item.id)}>{item.label}</button>)}
        </nav>
        <div className="account-controls">
          <div className="account-meta"><span>{user.name}</span><small>{roleLabel(user.role)}</small></div>
          <Button variant="soft" size="2" onClick={logout}>Sign out</Button>
        </div>
      </header>
      <div className="page-wrap" id="page-content">
        {pageError && <div className="page-alert" role="alert"><Text size="2">{pageError}</Text><Button size="1" variant="soft" onClick={() => void refresh()}>Retry</Button></div>}
        {refreshing && <div className="refresh-indicator"><Spinner size="1" /><Text size="1" color="gray">Updating workspace…</Text></div>}
        {user.role === "candidate" ? (
          <CandidateWorkspace
            user={user}
            profile={profile}
            programs={programs}
            registrations={registrations}
            appointments={appointments}
            notifications={notifications}
            onRefresh={refresh}
            onToast={setToast}
            onEditProfile={() => {
              shouldFocusProfile.current = true;
              setView("overview");
            }}
            view={view}
          />
        ) : (
          <StaffWorkspace
            user={user}
            view={view}
            programs={programs}
            candidates={candidates}
            registrations={registrations}
            stats={stats}
            quizzes={quizzes}
            appointments={appointments}
            onRefresh={refresh}
          />
        )}
      </div>
      {toast && <div className="toast-message" role="status">{toast}<button onClick={() => setToast("")} aria-label="Dismiss notification">×</button></div>}
      <footer className="app-footer">
        <span>SmartCampus AI</span>
        <span>Orientation suggestions require academic review. Sample data is not official.</span>
      </footer>
    </main>
  );
}

export default function Home() {
  return <AppWorkspace />;
}
