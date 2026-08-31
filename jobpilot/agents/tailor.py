"""The tailoring node: one JD and the profile in, an application packet out.

PRD §5.7. This is the first node that *writes claims about the author*, so it is
the first one the primary metric can score. Everything before it labelled or
looked things up.

Two design points carry most of the weight.

**The context is bullet-level, not a summary.** Triage gets
`triage_agent.profile_summary` because triage judges fit. The tailor is
selecting and rephrasing actual achievements, so it needs the bullets
themselves, their exact container names, and — critically — *which tools belong
to which container*. Handing it a flat tool list would invite the exact
overstatement the verifier exists to catch: a bullet built entirely from real
profile terms that attaches a real tool to the wrong employer.

**The `self_study` split is enforced in the context, not just the prose.** Tools
whose evidence points at no role or project are presented in a separate
skills-only list, because `classify_claim` will mark them `unplaced` if they
appear in an experience or project bullet. The instruction says so and the
context makes it visible.
"""

from __future__ import annotations

import json

from google.adk import Agent
from google.adk.models import BaseLlm
from pydantic import BaseModel, ConfigDict, Field

from jobpilot.agents import load_instruction
from jobpilot.ingest import JD
from jobpilot.profile.claims import SELF_STUDY, evidence_index
from jobpilot.profile.schema import Profile
from jobpilot.requirements import RequirementSet

INSTRUCTION = "tailor"
SELF_VERIFY_INSTRUCTION = "tailor_self_verify"


class TailoredDocs(BaseModel):
    """The packet, exactly PRD §4.4 minus the rendered PDF."""

    model_config = ConfigDict(extra="forbid")

    resume_md: str = Field(min_length=1)
    cover_letter_md: str = ""
    short_answers_md: str = ""
    self_review_notes: str = ""
    """What the model says it changed during self-review (`iter3a` only).

    Kept so the changelog can compare what it *claims* to have caught against
    what the verifier actually finds -- which is the whole question `iter3a`
    exists to answer."""

    ignored_keys: list[str] = Field(default_factory=list)
    """Top-level keys the model volunteered that the contract does not define.

    `extra="forbid"` stays: a *renamed* required field must still fail loudly,
    because that is a broken contract. But a model adding a chatty extra key
    beside three valid documents is not a broken contract, and discarding a
    whole packet over it loses real work -- it cost `jd_09` its packet on
    2026-08-30 (`short_answers_md_note`). Recorded here rather than dropped
    silently, so the trajectory shows exactly what was discarded."""

    def files(self) -> dict[str, str]:
        return {
            "resume.md": self.resume_md,
            "cover_letter.md": self.cover_letter_md,
            "short_answers.md": self.short_answers_md,
        }


def _preferences_block(profile: Profile) -> str:
    prefs = profile.writing_preferences
    lines = [
        f"- Resume length: at most {prefs.resume_max_pages} page(s).",
        f"- Voice: {prefs.voice}.",
    ]
    if prefs.no_single_bullet_projects:
        lines.append("- Never list a project with only one bullet.")
    if prefs.flag_gaps_instead_of_fabricating:
        lines.append(
            "- Where the posting asks for something the candidate lacks, leave "
            "it out entirely rather than hinting at it."
        )
    return "\n".join(lines)


def _tools_line(declared: list[str], from_evidence: set[str] | None) -> str:
    """A container's own tools, plus every tool whose evidence points at it."""
    return ", ".join(sorted(set(declared) | (from_evidence or set()))) or "none"


def tailoring_context(profile: Profile) -> str:
    """Everything the tailor may draw on, with placement made explicit."""
    # `evidence_index` is keyed by tool *and* every alias, so one entry appears
    # under several keys -- collect into sets or the lists repeat themselves.
    index = evidence_index(profile)
    placed: dict[str, set[str]] = {}
    skills_only: set[str] = set()
    for entry in index.values():
        if entry.where == SELF_STUDY:
            skills_only.add(entry.tool)
        else:
            placed.setdefault(entry.where, set()).add(entry.tool)

    out: list[str] = ["# Candidate material", ""]
    identity = profile.identity
    out += [
        "## Identity (use verbatim)",
        "",
        f"- Name: {identity.name}",
        f"- Location: {identity.location}",
        f"- Email: {identity.email}",
        f"- LinkedIn: {identity.linkedin}",
    ]
    if identity.github:
        out.append(f"- GitHub: {identity.github}")

    out += ["", "## Experience", ""]
    for exp in profile.experience:
        out += [
            f"### {exp.company} — {exp.title}   [{exp.id}]",
            f"Dates: {exp.start} to {exp.end or 'present'}",
            "Tools that belong to this role: "
            + _tools_line(exp.tools, placed.get(exp.id)),
            "Bullets you may select, reorder and rephrase:",
        ]
        out += [f"- {b.text}" for b in exp.bullets]
        out.append("")

    out += ["## Projects", ""]
    for proj in profile.projects:
        out += [
            f"### {proj.name}   [{proj.id}]",
            f"{proj.one_liner}",
            "Tools that belong to this project: "
            + _tools_line(proj.tools, placed.get(proj.id)),
            "Bullets you may select, reorder and rephrase:",
        ]
        out += [f"- {b.text}" for b in proj.bullets]
        out.append("")

    out += ["## Education", ""]
    for edu in profile.education:
        gpa = f", GPA {edu.gpa}" if edu.gpa is not None else ""
        out.append(
            f"### {edu.school}   [{edu.id}]\n"
            f"{edu.degree} {edu.field}, {edu.start} to {edu.end or 'present'}{gpa}"
        )
        if edu.coursework:
            out.append(f"Coursework: {', '.join(edu.coursework)}")
        out.append("")

    skills = profile.skills
    out += ["## Skills section material", ""]
    for bucket, values in skills.model_dump().items():
        if values:
            out.append(f"- {bucket.replace('_', ' ').title()}: {', '.join(values)}")

    if skills_only:
        out += [
            "",
            "## Skills-only tools — NOT usable in any Experience or Project bullet",
            "",
            "The candidate has used these outside any listed role or project, so "
            "there is no role to attach them to. They may appear in the Skills "
            "section and nowhere else:",
            "",
            f"{', '.join(sorted(skills_only))}",
        ]

    if profile.not_experienced:
        out += [
            "",
            "## Never claim these — the candidate has said they have not used them",
            "",
            f"{', '.join(sorted(e.tool for e in profile.not_experienced))}",
        ]
    return "\n".join(out)


def tailor_prompt(jd: JD, context: str, requirements: RequirementSet | None) -> str:
    """The material, then the posting. Requirements are a hint, never a target."""
    wanted = ""
    if requirements is not None:
        required = [r for r in requirements.requirements if r.required]
        if required:
            wanted = (
                "\n## What this posting requires\n\n"
                + "\n".join(f"- {r.name} ({r.type})" for r in required)
                + "\n\nEmphasise whatever the candidate genuinely has from this "
                "list. Say nothing about the rest.\n"
            )
    return (
        f"{context}\n\n"
        f"# The posting\n\n"
        f"{jd.company} — {jd.title}\nLocation: {jd.location}\n\n{jd.text}\n"
        f"{wanted}"
    )


def revision_prompt(
    jd: JD,
    context: str,
    document: str,
    failures: list[tuple[str, str, str]],
) -> str:
    """Ask for a corrected document. Deliberately self-contained.

    Everything the tailor needs is restated here -- the full material, the
    current document, and each rejected claim with its reason -- because a
    second `ctx.run_node` turn does *not* inherit the first turn's conversation
    (see `CLAUDE.md`). `iter3a` learned that the expensive way: its review turn
    answered "the candidate material was not included in this conversation" and
    emitted the apology as the resume.

    `failures` is (text, section, reason) per rejected claim.
    """
    listed = "\n\n".join(
        f"{i}. In the **{section}** section:\n"
        f"   > {text}\n"
        f"   Rejected because: {reason}"
        for i, (text, section, reason) in enumerate(failures, start=1)
    )
    return (
        f"{context}\n\n"
        f"# The posting\n\n"
        f"{jd.company} — {jd.title}\n\n"
        f"# The document you must correct\n\n"
        f"{document}\n\n"
        f"# What an independent verifier rejected\n\n"
        f"{listed}\n\n"
        "Fix each one. **Delete the unsupported claim — do not soften it.** "
        "\"Exposure to Kafka\" is the same fabrication as \"built Kafka "
        "pipelines\", only harder to catch, and a hedge that keeps the word is "
        "not a fix. If removing a claim leaves a bullet with nothing to say, "
        "remove the bullet.\n\n"
        "Change nothing else. Every other line is already verified, and "
        "rewriting it risks breaking a claim that currently holds. Keep the "
        "same markdown structure and the same section headings.\n\n"
        "Reply with the same single JSON object: resume_md, cover_letter_md, "
        "short_answers_md."
    )


def build_agent(
    profile: Profile,
    model: BaseLlm,
    meter: object | None = None,
    *,
    name: str = "tailor",
    self_verify: bool = False,
) -> Agent:
    """One agent. `name` must be unique per concurrent run (see agents/h1b.py).

    `self_verify` appends the review section to the instruction, so the model
    drafts and checks its own work inside **one** completion.

    This was a second `ctx.run_node` turn first, and it did not work: ADK scopes
    an agent's conversation to its own run, so the second turn could not see the
    first one's draft under `use_sub_branch` *or* a shared `override_branch`. It
    answered "the candidate material was not included in this conversation" and
    emitted that apology as the resume -- which scores as a document with no
    fabrications and no content, quietly poisoning the metric. One completion is
    also the more faithful reading of PRD 7.2's "self-verifies in own context":
    the draft and its critique share not just a session but a single forward
    pass. `iter3b` then moves the check to a node that cannot see any of it.
    """
    instruction = load_instruction(INSTRUCTION).replace(
        "{writing_preferences}", _preferences_block(profile)
    )
    if self_verify:
        instruction += "\n" + load_instruction(SELF_VERIFY_INSTRUCTION)
    return Agent(
        name=name,
        model=model,
        instruction=instruction,
        after_model_callback=meter,
    )


def parse_docs(reply: str) -> TailoredDocs:
    """Tolerates the model wrapping the object in prose, a fence, or extra keys."""
    from jobpilot.verify.llm import strip_fence

    text = strip_fence(reply)
    try:
        payload = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object, got {type(payload).__name__}")

    known = set(TailoredDocs.model_fields) - {"ignored_keys"}
    extra = sorted(set(payload) - known)
    docs = TailoredDocs.model_validate({k: v for k, v in payload.items() if k in known})
    docs.ignored_keys = extra
    return docs
