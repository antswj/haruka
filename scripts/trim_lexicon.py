#!/usr/bin/env python3
"""Build the runtime lexicon: data/ja_lints_research.json -> data/ja_lints_v1.json

WHY THIS SCRIPT EXISTS
----------------------
The research file is an archive. It carries, for all 247 entries, the note
explaining the entry, every source URL it came from, and — in 39 places — a
recorded disagreement between sources. That provenance is the reason the
lexicon is trustworthy, and it is exactly the wrong thing to ship into a
Lambda: it is 174KB of text no matcher will ever read.

So this script produces a second file that is only what the matcher needs.
The research file stays the record of WHY; the v1 file is the record of WHAT.
Neither is edited by hand, and this script is the only bridge between them —
which means any transform applied to the data is visible here, in one place,
rather than having been done once in an editor and forgotten.

Run:  python3 scripts/trim_lexicon.py
"""

import json
from pathlib import Path

# scripts/ -> repo root. Resolved from __file__ so the script works from any
# working directory, not just the repo root.
#
# INPUT lives in data/ (the archive, never deployed). OUTPUT lives in src/data/
# because template.yaml declares `CodeUri: src/` — only the CONTENTS of src/
# are packaged into the Lambda zip. A sibling data/ directory is invisible to
# the deployment, so a lexicon written there loads fine locally and dies at the
# first cold start in Lambda. Writing it inside src/ makes the zip
# self-contained: no env var, no build-time copy step, nothing to forget.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "ja_lints_research.json"
DST = ROOT / "src" / "data" / "ja_lints_v1.json"

# The only entry-level fields the matcher can use. Everything else —
# note, sources, disagreement — is provenance and stays in the archive.
#
# `confidence` is kept even though the filter already used it, because the
# severity mapping downstream needs to know an entry's level, not just that
# it passed. `action` / `category` / `kind` / `form` are the OTHER lists'
# classifiers; each appears on exactly one list, so this one set covers all
# four without special-casing.
KEEP_ENTRY_FIELDS = ("expression", "variants", "confidence", "action",
                     "category", "kind", "form")

# Section-level fields worth carrying, by the list that owns them.
# action_key and kind_key are three lines each and they DEFINE the values the
# code branches on — keeping them next to the entries means the meaning of
# "strip" is in the same file as the entries marked "strip".
KEEP_SECTION_FIELDS = ("label_ja", "description", "productive_patterns",
                       "suggested_fix_templates", "action_key", "kind_key")

# Only entries at or above this level are active rules. See split_entries().
ACTIVE_CONFIDENCE = ("high", "medium")

# --- The one editorial transform, declared out loud -------------------------
#
# 当該の〇〇 is listed as a variant of あの件, but 〇〇 is a PLACEHOLDER, not a
# character anyone types. As a literal needle it can only ever match text that
# contains the literal string "当該の〇〇" — which is to say, nothing. It is a
# repair template wearing a variant's clothes.
#
# So it moves to suggested_fix_templates, where templates live. The move is
# recorded on the entry it lands in (moved_from) and printed at build time,
# because a build script that silently rewrites its input is a build script
# nobody can audit.
RELOCATE_FROM_VARIANTS = ("vague_words", "あの件", "当該の〇〇")
RELOCATED_TEMPLATE = {
    "id": "specify_referent",
    "ja": "指示語を固有名詞で特定する",
    "example": "当該の〇〇 → 新商品『POOOTA！』の納期を5月4日（木）",
    "source": "https://next.rikunabi.com/journal/20160222_1/",
    "moved_from": "lists.vague_words.entries[あの件].variants",
    "note": ("Relocated by trim_lexicon.py: 〇〇 is a placeholder, so this "
             "string cannot match real text as a literal needle. It belongs "
             "with the fixes, not the match set."),
}


def slim(entry: dict) -> dict:
    """One entry, stripped to its matchable fields.

    Field ORDER follows KEEP_ENTRY_FIELDS rather than the source entry's own
    order, so every entry in the output file has the same shape and a diff
    between two builds shows real changes instead of key shuffling.
    """
    return {k: entry[k] for k in KEEP_ENTRY_FIELDS if k in entry}


def split_entries(entries: list) -> tuple[list, list]:
    """Active rules vs. info_level, by confidence.

    The rule is NOT "keep high and medium, drop the rest" — that would delete
    183 of 247 entries, because `confidence` exists on vague_words ONLY. The
    other three lists were never rated, and unrated is not the same as
    low-confidence. So:

      high | medium  -> active
      low             -> info_level (retained, fires at lower severity)
      absent          -> active, unrated

    An unrated entry is one nobody graded, and grading it here by omission
    would be inventing a judgment the research declined to make.
    """
    active, info = [], []
    for e in entries:
        conf = e.get("confidence")
        if conf is None or conf in ACTIVE_CONFIDENCE:
            active.append(slim(e))
        else:
            info.append(slim(e))
    return active, info


def surface_forms(entries: list) -> set:
    """Every string the matcher could match: expressions plus all variants."""
    forms = set()
    for e in entries:
        forms.add(e["expression"])
        forms.update(e["variants"])
    return forms


def relocate_placeholder(section: dict, list_name: str) -> bool:
    """Move 当該の〇〇 out of the match set and into the fix templates.

    Returns True if the move happened. False means the source data changed
    shape — reported, not crashed on, because a lexicon rebuild should not
    become a debugging session over one string.
    """
    target_list, target_expr, placeholder = RELOCATE_FROM_VARIANTS
    if list_name != target_list:
        return False

    for entry in section["entries"]:
        if entry["expression"] == target_expr and placeholder in entry["variants"]:
            entry["variants"] = [v for v in entry["variants"] if v != placeholder]
            templates = section["suggested_fix_templates"]["templates"]
            templates.append(RELOCATED_TEMPLATE)
            return True
    return False


def build() -> dict:
    research = json.loads(SRC.read_text(encoding="utf-8"))
    out_lists = {}
    report = {}

    for name, section in research["lists"].items():
        entries = section["entries"]
        active, info = split_entries(entries)

        out = {k: section[k] for k in KEEP_SECTION_FIELDS if k in section}
        out["entries"] = active
        # info_level is present on EVERY list, empty where nothing was rated
        # low. A consumer should never have to ask whether the key exists.
        out["info_level"] = info
        out_lists[name] = out

        moved = relocate_placeholder(out, name)

        report[name] = {
            "source_entries": len(entries),
            "high": sum(1 for e in entries if e.get("confidence") == "high"),
            "medium": sum(1 for e in entries if e.get("confidence") == "medium"),
            "low": sum(1 for e in entries if e.get("confidence") == "low"),
            "unrated": sum(1 for e in entries if "confidence" not in e),
            "active": len(active),
            "info_level": len(info),
            "surface_forms": len(surface_forms(active)),
            "relocated": moved,
        }

    meta = research["meta"]
    built = {
        "meta": {
            "name": "ja_lints_v1",
            "version": "1.0.0",
            "built_by": "scripts/trim_lexicon.py",
            "built_from": {
                "name": meta["name"],
                "version": meta["version"],
                "generated": meta["generated"],
            },
            "filter_rule": (
                "confidence high|medium -> entries; low -> info_level "
                "(retained, lower severity); absent -> entries (unrated). "
                "Only vague_words carries confidence."
            ),
            "dropped_entry_fields": ["note", "sources", "disagreement"],
            "counts": {k: {"active": v["active"], "info_level": v["info_level"]}
                       for k, v in report.items()},
        },
        "lists": out_lists,
    }
    return built, report


def main() -> None:
    built, report = build()

    DST.parent.mkdir(parents=True, exist_ok=True)

    # ensure_ascii=False: the whole file is Japanese. Escaped \uXXXX would
    # quadruple the size and make it unreadable in review.
    DST.write_text(
        json.dumps(built, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"read   {SRC.relative_to(ROOT)}")
    print(f"wrote  {DST.relative_to(ROOT)}  ({DST.stat().st_size:,} bytes)\n")

    head = (f"{'list':<16} {'src':>4} {'high':>5} {'med':>4} {'low':>4} "
            f"{'unrated':>8} {'active':>7} {'info':>5} {'forms':>6}")
    print(head)
    print("-" * len(head))
    totals = {k: 0 for k in ("source_entries", "high", "medium", "low",
                             "unrated", "active", "info_level", "surface_forms")}
    for name, r in report.items():
        print(f"{name:<16} {r['source_entries']:>4} {r['high']:>5} "
              f"{r['medium']:>4} {r['low']:>4} {r['unrated']:>8} "
              f"{r['active']:>7} {r['info_level']:>5} {r['surface_forms']:>6}")
        for k in totals:
            totals[k] += r[k]
    print("-" * len(head))
    print(f"{'TOTAL':<16} {totals['source_entries']:>4} {totals['high']:>5} "
          f"{totals['medium']:>4} {totals['low']:>4} {totals['unrated']:>8} "
          f"{totals['active']:>7} {totals['info_level']:>5} "
          f"{totals['surface_forms']:>6}")

    print()
    for name, r in report.items():
        if r["relocated"]:
            print(f"NOTE  {name}: 当該の〇〇 moved out of あの件.variants into "
                  f"suggested_fix_templates (placeholder, not a needle)")

    # The research file's own caveat disagrees with the research file's own
    # data. Printed rather than fixed: the archive is the record, and a build
    # script quietly reconciling it would hide the discrepancy from the next
    # person who reads the caveat and counts four.
    low_total = totals["low"]
    if low_total != 3:
        print(f"WARN  meta.caveats names THREE low-confidence vague entries "
              f"(サクッと/ちゃちゃっと/まるっと); the data holds {low_total} "
              f"(シュッと is also low). Data wins; caveat is stale.")


if __name__ == "__main__":
    main()
