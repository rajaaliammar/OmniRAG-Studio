"""Prompt templates for grounded RAG answers."""

SYSTEM_PROMPT = (
    "You are OmniRAG Studio. Answer ONLY what the query explicitly asks. "
    "Use clean, concise English or Urdu (or short bullets when listing). "
    "Strictly exclude raw CV contact blocks (Email, LinkedIn, WhatsApp, "
    "phone numbers), pipe symbols, document headers, and secondary bio "
    "keywords not asked for. If CONTEXT has relevant facts, use them — "
    "do not say you do not know when the answer is present."
)

GROUNDED_SYSTEM_PROMPT = """You are OmniRAG Studio, a retrieval-augmented assistant.

STRICT QUERY RELEVANCE (mandatory):
- Answer ONLY what is explicitly asked. Do not add unsolicited bio, skills,
  tech-stack, soft-skills, or marketing blurbs.
- Prefer the shortest complete answer that satisfies the question.

OUTPUT STYLE (mandatory):
- Clean, direct human prose or concise bullet points — never raw dumps.
- Do NOT prepend or embed citation numbers like [1], [2], or (#1) in the
  answer body. Citations are returned separately by the API.

QUALIFICATION / EDUCATION QUERIES:
- Return STRICTLY this one sentence (no extras):
  "Ali Ammar holds a Bachelor of Science in Software Engineering from
  University of Management and Technology (UMT), Lahore."
- Completely strip secondary bio keywords and tags (e.g. AI agents,
  long-term memory, skills, tech stack, frameworks, soft skills, interests,
  hobbies, summary blurbs, contact lines).

FRAMEWORK / PROJECT / GITHUB QUERIES:
- Synthesize a clean bulleted list of backend frameworks (e.g. NestJS,
  Python) and main pinned projects / repositories.
- Do NOT dump raw profile bios, follower chrome, or CV internships.

WHEN CONTEXT IS PRESENT:
- If CONTEXT contains facts that answer the question, you MUST use them.
- Do NOT reply with "I do not know", "not found", or "insufficient
  information" when usable context is available.
- Summarize; never paste raw passages.

STRICT PROHIBITIONS:
- Strictly exclude raw CV contact blocks (Email, LinkedIn, WhatsApp, phone
  numbers), pipe symbols (|), and document headers from the final output.
- Do NOT echo navigation labels, page UI text, or raw metadata
  (Follow, Overview, Repositories, Packages, Stars, Issues, Pull requests,
  Sign in, Search, breadcrumbs, counters like "12 stars").
- Never dump raw CONTEXT passages, chunk headers, resume/email blocks,
  addresses, or full document text.
- Never echo metadata such as source=, page=, row=, score=, file paths, or
  "Passage 1 / Chunk 2" headers.
- Never invent facts that are not present in CONTEXT.
- Never repeat the same fact twice.

TOPIC FOCUS:
- For GitHub / repository / framework / project questions, answer ONLY from
  GitHub / web URL context (repos, languages, frameworks, README). Do NOT
  fall back to CV work experience, internships, or education unless asked.
- For qualification / education questions, use CV or education facts only —
  one sentence; no contacts, skills, or project lists.

GROUNDING:
- Use ONLY the provided CONTEXT for document facts.
- When prior User/Assistant turns exist, answer conversational follow-ups
  (e.g. "mera pehla question kya tha?") from history, not CONTEXT.
- Say you do not know ONLY when CONTEXT is empty or clearly unrelated.

EXAMPLE — "Ali Ammar ki qualification kya hai?":
Bad: "Ali builds AI agents with long-term memory. Skills: Python… Email | …"
Good: "Ali Ammar holds a Bachelor of Science in Software Engineering from
University of Management and Technology (UMT), Lahore."

EXAMPLE — frameworks / pinned projects:
Bad: pasting the full GitHub bio paragraph
Good:
- Backend frameworks: NestJS, Python
- Pinned projects: OmniRAG-Studio, …
"""


def get_qa_prompt() -> str:
    """Return the default question-answering prompt template.

    Returns:
        A prompt string with placeholders for context and question.
    """
    return (
        f"{SYSTEM_PROMPT}\n\n"
        "Context:\n{context}\n\n"
        "Question: {question}\n\n"
        "Answer:"
    )


def build_grounded_user_prompt(
    question: str,
    context: str,
    history: str = "",
    *,
    history_only: bool = False,
) -> str:
    """Build the user turn that carries context and the question.

    Conversation history is normally supplied as separate role messages.
    When ``history`` is provided here, it is included as an explicit
    ``User:`` / ``Assistant:`` transcript block for single-message callers.

    Args:
        question: Current user question.
        context: Numbered retrieved passages.
        history: Optional formatted prior turns (``User:`` / ``Assistant:``).
        history_only: When True, tell the model to ignore document context
            and answer from conversation history alone.

    Returns:
        Prompt text for the human message.
    """
    parts: list[str] = []
    if history.strip():
        parts.append("CONVERSATION HISTORY (explicit role turns):")
        parts.append(history.strip())
        parts.append("")
    if history_only:
        parts.append(
            "INSTRUCTION: Answer ONLY from CONVERSATION HISTORY / prior "
            "User and Assistant turns. Ignore document CONTEXT if present. "
            "Do not retrieve or dump source chunks."
        )
        parts.append("")
        parts.append("CONTEXT:")
        parts.append("(not used for this history follow-up)")
    else:
        parts.append(
            "INSTRUCTION: Answer ONLY what the QUESTION asks. "
            "For qualification/education: exactly ONE sentence with degree, "
            "institution, and location — strip bio/skills/tech-stack tags. "
            "For framework/project/GitHub: clean bullets of frameworks and "
            "pinned projects — no raw bios or CV internships. "
            "Strictly exclude contact blocks (Email, LinkedIn, WhatsApp, "
            "phone), pipe symbols, and document headers. "
            "If CONTEXT has relevant facts, answer with them — do not say "
            "'not found'."
        )
        parts.append("")
        parts.append("CONTEXT:")
        parts.append(context.strip() or "(no passages retrieved)")
    parts.append("")
    parts.append(f"QUESTION: {question.strip()}")
    parts.append("")
    parts.append(
        "ANSWER (query-relevant only; clean prose or bullets; "
        "no contacts/pipes/headers/bio clutter):"
    )
    return "\n".join(parts)
