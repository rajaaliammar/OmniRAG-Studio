"""Tests for advanced RAG reasoning helpers and the eval suite."""

from __future__ import annotations

from backend.eval.eval_pipeline import (
    EvalCase,
    evaluate_case,
    main,
    report_to_dict,
    run_eval_suite,
    score_answer_relevance,
    score_context_recall,
    score_faithfulness,
)
from backend.rag.chain import (
    _expand_retrieval_queries,
    _needs_hybrid_history_retrieval,
    _rewrite_with_history,
)
from backend.rag.memory import ChatTurn as MemoryTurn
from backend.rag.prompts import GROUNDED_SYSTEM_PROMPT, build_grounded_user_prompt


def test_grounded_prompt_supports_multihop_and_hybrid() -> None:
    """System + user prompts must encode multi-hop and hybrid instructions."""
    assert "MULTI-HOP" in GROUNDED_SYSTEM_PROMPT
    assert "PARTIAL" in GROUNDED_SYSTEM_PROMPT.upper() or "partial" in GROUNDED_SYSTEM_PROMPT
    assert "HYBRID" in GROUNDED_SYSTEM_PROMPT
    assert "does not contain information about" in GROUNDED_SYSTEM_PROMPT
    hybrid_prompt = build_grounded_user_prompt(
        "And his degree?",
        context="Bachelor of Science in Software Engineering from UMT",
        history="User (turn 1): Tell me about Ali\nAssistant: Profile summary",
        hybrid=True,
    )
    assert "HYBRID" in hybrid_prompt
    assert "multi-hop" in hybrid_prompt.lower() or "partial" in hybrid_prompt.lower()
    assert "does not contain information about" in hybrid_prompt.lower()


def test_expand_retrieval_queries_boosts_multihop_and_aliases() -> None:
    """Compound questions should expand into focused retrieval variants."""
    variants = _expand_retrieval_queries(
        "What is his qualification and also his GitHub pinned projects?"
    )
    assert variants
    assert variants[0]
    joined = " ".join(variants).lower()
    assert "qualification" in joined or "bachelor" in joined
    assert "github" in joined or "pinned" in joined or "project" in joined
    assert len(variants) >= 2


def test_hybrid_history_rewrite_combines_prior_user_turn() -> None:
    """Follow-ups should rewrite with the previous user question for recall."""
    prior = [
        MemoryTurn(role="user", content="Tell me about Ali Ammar GitHub profile"),
        MemoryTurn(role="assistant", content="He has several repositories."),
    ]
    question = "And his degree from university?"
    assert _needs_hybrid_history_retrieval(question, prior)
    rewritten = _rewrite_with_history(question, prior)
    assert "GitHub" in rewritten or "Ali" in rewritten
    assert "degree" in rewritten.lower()


def test_pure_history_meta_is_not_hybrid() -> None:
    """Meta memory questions must stay history-only (not hybrid retrieval)."""
    prior = [MemoryTurn(role="user", content="What is my BS degree?")]
    assert not _needs_hybrid_history_retrieval("Mera pehla question kya tha?", prior)


def test_eval_metrics_score_precise_answers() -> None:
    """Core metrics should reward grounded, relevant, faithful answers."""
    context = (
        "Ali Ammar holds a Bachelor of Science in Software Engineering from UMT, "
        "Lahore."
    )
    answer = (
        "Ali Ammar holds a Bachelor of Science in Software Engineering from "
        "University of Management and Technology (UMT), Lahore."
    )
    assert score_context_recall(context, ("bachelor", "umt", "lahore")) >= 0.9
    assert (
        score_answer_relevance(
            "Ali Ammar ki qualification kya hai?",
            answer,
            ("bachelor", "software engineering", "umt"),
        )
        >= 0.7
    )
    assert score_faithfulness(answer, context) >= 0.4


def test_eval_faithfulness_penalizes_generic_fallback() -> None:
    """Fallback refusals must score 0 faithfulness when context exists."""
    context = "Bachelor of Science in Software Engineering from UMT Lahore"
    answer = "I could not find relevant information in the indexed sources."
    assert score_faithfulness(answer, context) == 0.0


def test_run_eval_suite_offline_passes_threshold() -> None:
    """Offline suite should clear the default mean quality bar."""
    report = run_eval_suite(offline=True)
    assert report.mode == "offline"
    assert len(report.scores) >= 5
    assert report.averages.mean >= 0.55
    payload = report_to_dict(report)
    assert "averages" in payload
    assert "cases" in payload


def test_eval_cli_main_offline_exits_zero() -> None:
    """``python -m backend.eval.eval_pipeline`` offline path should succeed."""
    assert main(["--json", "--min-mean", "0.55"]) == 0


def test_evaluate_case_unseen_complex_fixture() -> None:
    """Unseen/complex fixture must remain direct and precise."""
    case = EvalCase(
        case_id="custom_unseen",
        category="complex",
        question="Which backend frameworks appear in the notes?",
        expected_answer_keywords=("nestjs", "python"),
        context_gold_keywords=("nestjs", "python"),
        context="Backend: NestJS and Python services.",
        answer="- Backend frameworks: NestJS, Python",
    )
    scores = evaluate_case(case)
    assert scores.context_recall >= 0.9
    assert scores.answer_relevance >= 0.7
    assert scores.faithfulness >= 0.4
