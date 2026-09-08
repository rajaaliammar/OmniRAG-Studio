"""Automated RAG evaluation suite: recall, relevance, and faithfulness.

Run from the project root::

    python -m backend.eval.eval_pipeline
    python -m backend.eval.eval_pipeline --collection default_collection
    python -m backend.eval.eval_pipeline --offline
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Sequence

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "for",
        "to",
        "of",
        "in",
        "on",
        "is",
        "are",
        "was",
        "were",
        "be",
        "as",
        "at",
        "by",
        "from",
        "that",
        "this",
        "it",
        "with",
        "what",
        "which",
        "how",
        "who",
        "where",
        "when",
        "kya",
        "hai",
        "ki",
        "ke",
        "ka",
    }
)


@dataclass(frozen=True)
class EvalCase:
    """One evaluation question with gold signals for offline scoring."""

    case_id: str
    question: str
    expected_answer_keywords: tuple[str, ...]
    context_gold_keywords: tuple[str, ...]
    category: str = "standard"
    # Optional pre-baked context/answer for fully offline runs.
    context: str = ""
    answer: str = ""


@dataclass(frozen=True)
class EvalScores:
    """Metric bundle for a single case."""

    context_recall: float
    answer_relevance: float
    faithfulness: float

    @property
    def mean(self) -> float:
        """Average of the three core metrics."""
        return round(
            (self.context_recall + self.answer_relevance + self.faithfulness) / 3.0,
            4,
        )


@dataclass
class EvalReport:
    """Aggregate report across the suite."""

    scores: dict[str, EvalScores] = field(default_factory=dict)
    answers: dict[str, str] = field(default_factory=dict)
    mode: str = "offline"

    @property
    def averages(self) -> EvalScores:
        """Mean metrics across all cases."""
        if not self.scores:
            return EvalScores(0.0, 0.0, 0.0)
        n = len(self.scores)
        return EvalScores(
            context_recall=round(
                sum(item.context_recall for item in self.scores.values()) / n,
                4,
            ),
            answer_relevance=round(
                sum(item.answer_relevance for item in self.scores.values()) / n,
                4,
            ),
            faithfulness=round(
                sum(item.faithfulness for item in self.scores.values()) / n,
                4,
            ),
        )


def _tokenize(text: str) -> set[str]:
    """Lowercase content tokens without stopwords."""
    tokens = _TOKEN_RE.findall((text or "").lower())
    return {token for token in tokens if len(token) > 1 and token not in _STOPWORDS}


def _keyword_coverage(required: Sequence[str], haystack: str) -> float:
    """Fraction of required keywords present in haystack (case-insensitive)."""
    if not required:
        return 1.0
    lowered = (haystack or "").lower()
    hits = 0
    for keyword in required:
        key = (keyword or "").strip().lower()
        if not key:
            continue
        if key in lowered or all(part in lowered for part in key.split()):
            hits += 1
    return round(hits / max(len(required), 1), 4)


def score_context_recall(context: str, gold_keywords: Sequence[str]) -> float:
    """Context Recall: share of gold facts present in retrieved context."""
    return _keyword_coverage(gold_keywords, context)


def score_answer_relevance(
    question: str,
    answer: str,
    expected_keywords: Sequence[str],
) -> float:
    """Answer Relevance: keyword + lexical overlap with the question intent."""
    keyword_score = _keyword_coverage(expected_keywords, answer)
    q_tokens = _tokenize(question)
    a_tokens = _tokenize(answer)
    if not q_tokens or not a_tokens:
        lexical = 0.0
    else:
        lexical = len(q_tokens & a_tokens) / len(q_tokens)
    # Prefer gold keyword coverage; lexical overlap is a soft assist.
    return round(min(1.0, (0.75 * keyword_score) + (0.25 * lexical)), 4)


def score_faithfulness(answer: str, context: str) -> float:
    """Faithfulness: fraction of answer content tokens supported by context.

    Generic refusal / empty answers score 0 when context is non-empty, so the
    suite penalizes fallback responses that ignore usable evidence.
    """
    cleaned_answer = (answer or "").strip()
    cleaned_context = (context or "").strip()
    if not cleaned_answer:
        return 0.0
    refusal_markers = (
        "could not find relevant information",
        "i do not know",
        "not found",
        "insufficient information",
    )
    lowered_answer = cleaned_answer.lower()
    # Exact OOD guardrail sentence is intentional and treated as faithful.
    if "the provided context does not contain information about" in lowered_answer:
        return 1.0
    if cleaned_context and any(marker in lowered_answer for marker in refusal_markers):
        return 0.0
    if not cleaned_context:
        return 0.0

    answer_tokens = _tokenize(cleaned_answer)
    context_tokens = _tokenize(cleaned_context)
    if not answer_tokens:
        return 0.0
    supported = len(answer_tokens & context_tokens)
    return round(supported / len(answer_tokens), 4)


def evaluate_case(
    case: EvalCase,
    *,
    context: str | None = None,
    answer: str | None = None,
) -> EvalScores:
    """Score one case given (or baked-in) context and answer strings."""
    ctx = context if context is not None else case.context
    ans = answer if answer is not None else case.answer
    return EvalScores(
        context_recall=score_context_recall(ctx, case.context_gold_keywords),
        answer_relevance=score_answer_relevance(
            case.question,
            ans,
            case.expected_answer_keywords,
        ),
        faithfulness=score_faithfulness(ans, ctx),
    )


def default_eval_cases() -> list[EvalCase]:
    """Standard + unseen/complex cases used by the CLI suite."""
    return [
        EvalCase(
            case_id="std_education",
            category="standard",
            question="Ali Ammar ki qualification kya hai?",
            expected_answer_keywords=(
                "bachelor",
                "software engineering",
                "umt",
                "lahore",
            ),
            context_gold_keywords=(
                "bachelor",
                "software engineering",
                "umt",
                "lahore",
            ),
            context=(
                "Ali Ammar holds a Bachelor of Science in Software Engineering "
                "from University of Management and Technology (UMT), Lahore. "
                "Email: ali@example.com Skills: AI agents"
            ),
            answer=(
                "Ali Ammar holds a Bachelor of Science in Software Engineering "
                "from University of Management and Technology (UMT), Lahore."
            ),
        ),
        EvalCase(
            case_id="std_github_projects",
            category="standard",
            question="What are Ali Ammar's GitHub pinned projects and frameworks?",
            expected_answer_keywords=("omnirag", "python", "nestjs"),
            context_gold_keywords=(
                "pinned repository",
                "omnirag-studio",
                "python",
                "nestjs",
            ),
            context=(
                "Pinned repository: OmniRAG-Studio — Multi-source RAG chatbot "
                "(Language: Python)\n"
                "Pinned repository: api-gateway — NestJS backend service"
            ),
            answer=(
                "- Backend frameworks: NestJS, Python\n"
                "- Pinned projects: OmniRAG-Studio; api-gateway"
            ),
        ),
        EvalCase(
            case_id="std_backend_stack",
            category="standard",
            question="What is the backend tech stack?",
            expected_answer_keywords=(
                "python",
                "typescript",
                "postgresql",
                "qdrant",
                "nestjs",
                "fastapi",
            ),
            context_gold_keywords=(
                "python",
                "typescript",
                "postgresql",
                "nestjs",
            ),
            context=(
                "Backend stack: Python, TypeScript, NestJS, FastAPI, "
                "PostgreSQL, Qdrant. Frontend: React, Next.js."
            ),
            answer=(
                "Programming Languages: Python, TypeScript\n"
                "Databases: PostgreSQL, Qdrant\n"
                "Frameworks: NestJS, FastAPI"
            ),
        ),
        EvalCase(
            case_id="ood_favorite_movie",
            category="complex",
            question="What is Ali's favorite movie?",
            expected_answer_keywords=("does not contain", "favorite movie"),
            context_gold_keywords=("software engineering", "umt"),
            context=(
                "Ali Ammar holds a BS in Software Engineering from UMT. "
                "Skills: Python, NestJS. Bio dump should not be used."
            ),
            answer=(
                "The provided context does not contain information about "
                "favorite movie."
            ),
        ),
        EvalCase(
            case_id="complex_multihop_study",
            category="complex",
            question=(
                "Based on his profile, where did he complete software "
                "engineering studies and which city was that in?"
            ),
            expected_answer_keywords=("umt", "lahore", "software engineering"),
            context_gold_keywords=(
                "software engineering",
                "university of management and technology",
                "lahore",
            ),
            context=(
                "Education: BS Software Engineering, University of Management "
                "and Technology (UMT), Lahore. Internships at Acme Corp."
            ),
            answer=(
                "He completed Software Engineering studies at University of "
                "Management and Technology (UMT), Lahore."
            ),
        ),
        EvalCase(
            case_id="unseen_partial_synthesis",
            category="complex",
            question=(
                "If CONTEXT only lists NestJS and Python under backend skills, "
                "what backend frameworks does the profile use?"
            ),
            expected_answer_keywords=("nestjs", "python"),
            context_gold_keywords=("nestjs", "python", "backend"),
            context=(
                "Backend stack notes: NestJS services and Python tooling. "
                "No mobile stack listed."
            ),
            answer="- Backend frameworks: NestJS, Python",
        ),
        EvalCase(
            case_id="unseen_hybrid_followup",
            category="complex",
            question="And his degree title from that university?",
            expected_answer_keywords=(
                "bachelor",
                "software engineering",
            ),
            context_gold_keywords=(
                "bachelor of science",
                "software engineering",
                "umt",
            ),
            context=(
                "Prior turn discussed UMT Lahore. Document says: Bachelor of "
                "Science in Software Engineering from UMT."
            ),
            answer="Bachelor of Science in Software Engineering.",
        ),
        EvalCase(
            case_id="faithfulness_no_hallucination",
            category="complex",
            question="What GPA did Ali Ammar graduate with?",
            expected_answer_keywords=("umt", "software engineering"),
            context_gold_keywords=("software engineering", "umt"),
            context=(
                "Ali Ammar studied Software Engineering at UMT Lahore. "
                "No GPA is listed in the document."
            ),
            # Faithful: does not invent a GPA; stays within context tokens.
            answer=(
                "The document lists Software Engineering at UMT Lahore but "
                "does not list a GPA."
            ),
        ),
    ]


def run_eval_suite(
    cases: Sequence[EvalCase] | None = None,
    *,
    offline: bool = True,
    collection_name: str = "default_collection",
    answer_fn: Callable[[str, str], tuple[str, str]] | None = None,
) -> EvalReport:
    """Evaluate standard + complex cases and return an aggregate report.

    Args:
        cases: Optional custom cases; defaults to :func:`default_eval_cases`.
        offline: When True, score baked-in context/answers (no vector store).
        collection_name: Collection used for live retrieval/generation.
        answer_fn: Optional ``(question, collection) -> (answer, context)``.

    Returns:
        Populated :class:`EvalReport`.
    """
    selected = list(cases or default_eval_cases())
    report = EvalReport(mode="offline" if offline else "live")

    live_fn = answer_fn
    if not offline and live_fn is None:
        live_fn = _default_live_answer_fn

    for case in selected:
        if offline or live_fn is None:
            scores = evaluate_case(case)
            report.answers[case.case_id] = case.answer
        else:
            try:
                answer, context = live_fn(case.question, collection_name)
            except Exception as exc:  # pragma: no cover - live path
                logger.warning("Live eval failed for %s: %s", case.case_id, exc)
                answer, context = "", ""
            scores = evaluate_case(case, context=context, answer=answer)
            report.answers[case.case_id] = answer
        report.scores[case.case_id] = scores
    return report


def _default_live_answer_fn(question: str, collection_name: str) -> tuple[str, str]:
    """Live path: run the RAG chain and rebuild a context string from citations."""
    from backend.rag.chain import answer_query

    result = answer_query(question, collection_name)
    context_bits: list[str] = []
    for citation in result.citations:
        snippet = str(citation.get("snippet") or "").strip()
        source = str(citation.get("source") or "").strip()
        if snippet:
            context_bits.append(f"{source}: {snippet}" if source else snippet)
        elif source:
            context_bits.append(source)
    return result.answer, "\n".join(context_bits)


def report_to_dict(report: EvalReport) -> dict[str, Any]:
    """Serialize a report for JSON / CLI output."""
    averages = report.averages
    return {
        "mode": report.mode,
        "averages": asdict(averages) | {"mean": averages.mean},
        "cases": {
            case_id: {
                "scores": asdict(scores) | {"mean": scores.mean},
                "answer": report.answers.get(case_id, ""),
            }
            for case_id, scores in report.scores.items()
        },
    }


def _print_report(report: EvalReport) -> None:
    """Pretty-print metrics to stdout."""
    payload = report_to_dict(report)
    averages = payload["averages"]
    print("OmniRAG Eval Suite")
    print(f"Mode: {payload['mode']}")
    print(
        "Averages - "
        f"context_recall={averages['context_recall']:.3f}  "
        f"answer_relevance={averages['answer_relevance']:.3f}  "
        f"faithfulness={averages['faithfulness']:.3f}  "
        f"mean={averages['mean']:.3f}"
    )
    print("-" * 64)
    for case_id, body in payload["cases"].items():
        scores = body["scores"]
        print(
            f"{case_id:28} "
            f"R={scores['context_recall']:.2f} "
            f"Rel={scores['answer_relevance']:.2f} "
            f"F={scores['faithfulness']:.2f} "
            f"mean={scores['mean']:.2f}"
        )


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m backend.eval.eval_pipeline",
        description=(
            "Run OmniRAG evaluation for Context Recall, Answer Relevance, "
            "and Faithfulness."
        ),
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call the live RAG chain against a Chroma collection.",
    )
    parser.add_argument(
        "--collection",
        default="default_collection",
        help="Collection name for --live mode.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a table.",
    )
    parser.add_argument(
        "--min-mean",
        type=float,
        default=0.55,
        help="Exit non-zero if the suite mean score falls below this threshold.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for ``python -m backend.eval.eval_pipeline``."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    offline = not bool(args.live)
    report = run_eval_suite(
        offline=offline,
        collection_name=args.collection,
    )
    if args.json:
        print(json.dumps(report_to_dict(report), indent=2))
    else:
        _print_report(report)

    mean = report.averages.mean
    if mean < float(args.min_mean):
        logger.error(
            "Eval mean %.3f is below threshold %.3f",
            mean,
            args.min_mean,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
