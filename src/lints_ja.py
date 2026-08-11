"""Japanese deterministic lints (PLAN §9, JA rulebook).

Five pure functions over one loaded lexicon. Nothing here calls Bedrock,
nothing here is wired into a route, and nothing here decides a score —
these produce findings, and something else will later decide what a pile of
findings is worth.

PRIVACY INVARIANT — this module does not import `logging` and must not.
Findings carry the matched span, which is user text. That span travels in the
return value and nowhere else. app.py already established the rule (its 400
handler logs a LENGTH, never a body); this file's version of that rule is
simply that there is no logger to misuse. If you ever need to debug a match,
return it, do not print it.

COLD-START LOADING — LEXICON is read once at import. On Lambda, import runs
once per cold start and the module object is reused across invocations, so a
module-level read is a per-container cost, not a per-request one. Same
reasoning as `lifespan="off"` in app.py: work that does not change between
requests does not belong on the request path.

TODO(aggregator) — three constraints the research states that FIVE INDEPENDENT
PURE FUNCTIONS STRUCTURALLY CANNOT HONOR. They are not bugs here; they are
work for whatever combines these findings into a score.

  1. Ordering. cross_list_notes[2]: cushions must be detected BEFORE task
     verbs, because some cushions contain verbs (お伺いしたいことがあるのですが).
     Five functions with no shared state have no ordering. The aggregator has
     to consume cushion spans first.

  2. Same-span double-fire. cross_list_notes[0]: 14 surface forms live in two
     lists, and わかりやすく / 詳しく are full ENTRIES in both vague_words and
     format_markers. Both rules will fire on the same span. Each function
     de-duplicates within itself (see _scan) but cannot see the others.
     The note says do not let both fire visibly — that is a scoring decision.

     One case is not incidental but GUARANTEED, and it is this module's own
     doing: check_ambiguous_referent draws its needles from two vague_words
     entries, so every referent hit is also a vague hit. 「例の件」 returns a
     vague_word warning AND an ambiguous_referent warning, always. The
     aggregator must collapse the pair — the referent finding is the more
     specific of the two and should be the one that survives.

  3. Cushion stacking density. matching_notes[0]: stacking is the defect, not
     any single cushion. check_cushion_padding reports every occurrence so the
     count survives; turning "three cushions in the head" into a signal is the
     aggregator's job.

And one Tailor rule that belongs nowhere else yet — cross_list_notes[1] and
VERDICT.md: 適切に must NEVER be offered as a fix. Japanese politeness guides
recommend it as the upgrade for ざっくり／適当な while prompt guides list it as
an NG word, so a de-vaguing rewrite can trip this very rulebook.
"""

import json
import os
import re
from pathlib import Path

# --- Loading ---------------------------------------------------------------
#
# Path via env var, matching how JUDGE_MODEL_ID and TIKTOKEN_CACHE_DIR already
# work in this project: the code reads a variable, the template declares its
# value. The default resolves to the repo layout so this module is importable
# and testable right now, before any packaging decision is made.
#
# TODO(day 4) — PACKAGING. template.yaml has `CodeUri: src/`, so the CONTENTS
# of src/ land at /var/task and data/ (a sibling of src/) is NOT in the zip.
# Two ways out, both one line: set JA_LEXICON_PATH in the template and copy
# data/ja_lints_v1.json into the build, or move the build script's output into
# src/. Deferred deliberately — today's task wires nothing into routes.
_DEFAULT_LEXICON_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "ja_lints_v1.json"
)
LEXICON_PATH = Path(os.environ.get("JA_LEXICON_PATH", _DEFAULT_LEXICON_PATH))

PRODUCTIVE_VAGUE = re.compile(r"(な|した|っぽい|てる|ている|ある)(感じ|具合)(で|に)")

def load_lexicon(path: Path | None = None) -> dict:
    """Read the built lexicon. One artifact, one loader path.

    Only data/ja_lints_v1.json is ever read. The 174KB research file is the
    archive — it holds every note, source URL and recorded disagreement, and
    none of that is matchable, so it never enters the deployment package.

    Failure is loud on purpose. A missing lexicon means every lint silently
    returns nothing, which looks exactly like a clean prompt. Better to refuse
    to start than to score a bad prompt as good.
    """
    target = Path(path) if path else LEXICON_PATH
    if not target.exists():
        raise FileNotFoundError(
            f"JA lexicon not found at {target}. "
            f"Build it with: python3 scripts/trim_lexicon.py "
            f"(or set JA_LEXICON_PATH)."
        )
    return json.loads(target.read_text(encoding="utf-8"))


LEXICON = load_lexicon()


# --- Shared matcher --------------------------------------------------------

# Needles removed from EVERY list's match set, not just one rule's.
#
# あれ is two characters and it is a variant of the あの件 entry — which lives
# in vague_words, so it is live in check_vague_words AND check_ambiguous_
# referent. Measured against the lexicon itself, bare あれ is a substring of
# seven cushion surface forms: 可能であれば / もし可能であれば / もしも可能であれば /
# お力になれることがあれば / 私でお力になれることがあれば / 私にできることがあれば /
# もし私にできることがあれば. A raw substring scan therefore reports "ambiguous
# referent" — and "vague" at WARNING severity — on an ordinary politeness
# phrase.
#
# Excluded rather than patched, because the fix is a boundary check and
# boundaries are a regex. That regex is Anthony's, same as the productive
# pattern below. Delete the entry from this set once it exists.
_EXCLUDED_NEEDLES = frozenset({"あれ"})


def _finding(rule: str, matched: str, action: str | None, severity: str) -> dict:
    """The one finding shape, built in one place.

    Exactly four keys. `action` is None everywhere except cushions, where it
    carries the strip/flag/keep class so the Tailor cannot strip a cushion
    that was encoding a real constraint.
    """
    return {
        "rule": rule,
        "matched": matched,
        "action": action,
        "severity": severity,
    }


def _needles(entries: list, severity: str) -> list:
    """(needle, entry, severity) triples — one per matchable surface form.

    An entry's expression and its variants are all equal as needles; the
    expression is not privileged, it is just the label the research filed the
    family under.
    """
    triples = []
    for entry in entries:
        for form in (entry["expression"], *entry["variants"]):
            if form in _EXCLUDED_NEEDLES:
                continue
            triples.append((form, entry, severity))
    return triples


def _overlaps(start: int, end: int, claimed: list) -> bool:
    return any(start < c_end and end > c_start for c_start, c_end in claimed)


def _scan(text: str, triples: list, *, one_per_entry: bool) -> list:
    """Find needles in text. Longest wins, spans are claimed once.

    Two rules, both doing real work:

    LONGEST FIRST. Sorting by needle length descending means いい感じにまとめといて
    is reported as itself rather than as the いい感じ hiding inside it, and it
    is what stops the bare referents from double-reporting: それ is a substring
    of それら, so それら claims the span first and それ never sees it.

    CLAIMED SPANS. A character position is reported at most once per check.
    Without this, one 5-character phrase could produce a finding for every
    variant it contains — 64 entries would become hundreds of findings over
    the same text.

    one_per_entry=True  -> at most one finding per lexicon entry (the default;
                           an entry is a family, and the family fired once).
    one_per_entry=False -> every non-overlapping occurrence (cushions only,
                           where matching_notes[0] says repetition IS the
                           signal: "match greedily and repeatedly from
                           position 0").

    Returns (start, needle, entry, severity) sorted by position, so findings
    come back in reading order rather than in needle-length order.
    """
    claimed: list = []
    hits: list = []
    fired: set = set()

    for needle, entry, severity in sorted(
        triples, key=lambda t: len(t[0]), reverse=True
    ):
        # Expressions are unique within a list, so the expression is a safe
        # entry key. (わかりやすく and 詳しく appear in two lists — but never
        # twice in the same one, and a check only ever scans one list.)
        expression = entry["expression"]
        if one_per_entry and expression in fired:
            continue

        start = text.find(needle)
        while start != -1:
            end = start + len(needle)
            if not _overlaps(start, end, claimed):
                claimed.append((start, end))
                hits.append((start, needle, entry, severity))
                fired.add(expression)
                if one_per_entry:
                    break
            start = text.find(needle, start + 1)

    hits.sort(key=lambda h: h[0])
    return hits


def _contains_any(text: str, entries: list) -> bool:
    """Presence only, for the inverted checks.

    Deliberately does NOT collect spans. The inverted rules report an ABSENCE,
    so a matched span would be information the finding has no field for — and
    not capturing user text you have no use for is the cheaper kind of privacy.
    """
    for entry in entries:
        for form in (entry["expression"], *entry["variants"]):
            if form in _EXCLUDED_NEEDLES:
                continue
            if form in text:
                return True
    return False


# --- 1. Vague / hands-off wording ------------------------------------------

def check_vague_words(text: str, lexicon: dict = LEXICON) -> list:
    """あいまい・丸投げ表現 — wordlist match only.

    Severity follows the research's own grading: high and medium entries are
    warnings, the four info_level entries (サクッと / ちゃちゃっと / まるっと /
    シュッと) fire at info. VERDICT.md is explicit that firing サクッと at the
    same severity as いい感じに "would not be defensible from the evidence" —
    no Japanese source treats it as problematic, so it teaches without
    accusing.
    """
    
    section = lexicon["lists"]["vague_words"]
    triples = (
        _needles(section["entries"], "warning")
        + _needles(section["info_level"], "info")
    )

    findings = [
        _finding("vague_word", needle, None, severity)
        for _, needle, _entry, severity in _scan(text, triples, one_per_entry=True)
    ]

    for m in PRODUCTIVE_VAGUE.finditer(text):
        findings.append({"rule": "vague_word", "matched": m.group(0), "action": None, "severity": "warning"})
        
    return findings


# --- 2. Cushion padding ----------------------------------------------------

# action_key, straight from the research file:
#   strip — "True zero-information padding. Safe to discount entirely."
#   flag  — "Encodes a real constraint (grants an out, waives urgency).
#            Discounting it silently upgrades a soft ask to a hard one."
#   keep  — "Not padding at all — asserts a fact. Removing it deletes
#            information."
#
# Only strip is a defect worth warning about. flag and keep are reported at
# info because the user should not be told to delete them — they are context
# for the Tailor, not faults in the prompt.
_CUSHION_SEVERITY = {"strip": "warning", "flag": "info", "keep": "info"}


def check_cushion_padding(text: str, lexicon: dict = LEXICON) -> list:
    """クッション言葉 — every occurrence, because stacking is the defect.

    matching_notes[0]: "Cushions STACK, and the Japanese sources treat
    stacking as the defect rather than any individual phrase... A prompt head
    can carry three in a row (お忙しいところ + 大変恐縮ではございますが +
    お手数をおかけしますが). Match greedily and repeatedly from position 0."

    So this is the one check that does not collapse to one finding per entry.

    EVERY finding carries `action`, not just flag and keep. The requirement
    was that flag and keep must carry it so the Tailor never strips them; a
    Tailor that always receives the class cannot mishandle the one case where
    it happens to be missing.
    """
    entries = lexicon["lists"]["cushion_words"]["entries"]

    triples = []
    for entry in entries:
        triples += _needles([entry], _CUSHION_SEVERITY[entry["action"]])

    return [
        _finding("cushion_padding", needle, entry["action"], severity)
        for _, needle, entry, severity in _scan(text, triples, one_per_entry=False)
    ]


# --- 3. Task verb present (INVERTED) ---------------------------------------

def check_task_verb_present(text: str, lexicon: dict = LEXICON) -> list:
    """明確な依頼表現 — returns a finding when NO task verb is found.

    Inverted: the lexicon here is positive signal, so the finding is the
    absence. A prompt that never names an action is the defect.

    `matched` is "" — the declared shape makes only `action` nullable, and an
    absence has no span to report.

    Known gap, from matching_notes[2]: this matches on raw strings, so 要約 as
    a bare noun in running text ("要約の品質について") counts as a task verb when
    it should not. The fix is part-of-speech matching, which is the SudachiPy
    question — see the 表記ゆれ note.
    """
    entries = lexicon["lists"]["task_verbs"]["entries"]
    if _contains_any(text, entries):
        return []
    return [_finding("task_verb_missing", "", None, "warning")]


# --- 4. Output format marker (INVERTED) ------------------------------------

def check_format_marker(text: str, lexicon: dict = LEXICON) -> list:
    """出力形式マーカー — returns a finding when NO format marker is found.

    Same inverted shape as the task verb check. Warning rather than info
    because PLAN §9 makes "output indicator" one of the five rubric bars, so
    a missing one is a real deduction, not trivia.

    Worth remembering when this feeds a score — meta.caveats: length markers
    (〜文字以内で) are detectable, but "multiple Japanese verification articles
    report that LLMs frequently fail to obey them. Detecting the marker is not
    the same as the constraint being honored."
    """
    entries = lexicon["lists"]["format_markers"]["entries"]
    if _contains_any(text, entries):
        return []
    return [_finding("format_marker_missing", "", None, "warning")]


# --- 5. Ambiguous referent -------------------------------------------------

# 指示語 (こそあど) reference to context the reader does not have. The research
# never tagged entries by type, so the selection is HERE, by name, where it can
# be read and argued with — rather than hidden in the build script as an
# invented field. The matched strings still come entirely from the lexicon.
#
#   あの件         -> 例の件 / 例のアレ / その辺 / そのあたり / これら / それら
#                     (あれ excluded above; 当該の〇〇 relocated to the fix
#                      templates by trim_lexicon.py — a placeholder is not a
#                      needle)
#   前と同じような -> 前と同じようなやつで / いつもの感じで / この前みたいに / 例のやつで
#
_REFERENT_EXPRESSIONS = ("あの件", "前と同じような")

# Bare こそあど, added by hand because the lexicon has neither: それ and これ
# appear only inside それら / これら. Genuinely ambiguous, but far too common
# in harmless prompts to accuse at warning level — so they teach at info.
#
# KNOWN LIMITATION, same territory as あれ. Bare それ is a substring of five
# lexicon forms: それなりに / それなり / それなりの / それっぽく / それっぽい.
# Those belong to OTHER vague entries, so _scan's claimed spans (which are
# per-check) cannot suppress them — 「それなりに」 will produce an info finding
# here. A boundary regex fixes it; that regex is yours, and the research
# already sketched the seam it fills:
#   lexicon["lists"]["vague_words"]["productive_patterns"][1]["regex_sketch"]
#     = (?:あの|例の|その|この)(?:件|やつ|アレ|あたり|辺)
_BARE_REFERENTS = ("それ", "これ")


def check_ambiguous_referent(text: str, lexicon: dict = LEXICON) -> list:
    """指示語 with no antecedent — それ / あれ / 例のやつ and family.

    Two severities in one check: the lexicon families warn, the bare こそあど
    inform. They share one scan so that longest-wins applies across both —
    which is exactly what keeps それら from also reporting a bare それ.
    """
    entries = lexicon["lists"]["vague_words"]["entries"]
    referents = [e for e in entries if e["expression"] in _REFERENT_EXPRESSIONS]

    # Synthesised entries so the bare forms flow through the same matcher.
    # Empty variants: these are single surface forms, not families.
    bare = [{"expression": r, "variants": []} for r in _BARE_REFERENTS]

    triples = _needles(referents, "warning") + _needles(bare, "info")

    return [
        _finding("ambiguous_referent", needle, None, severity)
        for _, needle, _entry, severity in _scan(text, triples, one_per_entry=True)
    ]
