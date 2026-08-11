# Haruka — BUILD_STATE
Date: 2026-08-12 (small hours) · Day 3 (end)

## DONE
- /analyze LIVE end-to-end: validate → detect_language → judge (Converse, jp. profile)
  → parse (fence-strip + strict contract) → 5 JA lints (collapsed) → counts → §8 shape
- GATES GREEN, both languages:
  - JA consistency 3×: spread ±0 · EN 3×: spread ±1 (gate ±1)
  - Calibration: good prompts score high with input_data correctly held low (materials missing)
  - Jailbreak JA+EN: graded not obeyed — zeros + verdict naming the attack. Fence held
  - JA native-phrasing eye test: [Anthony's verdict here]
- JA lints shipped: 5 checks, strip/flag/keep triage, referent-over-vague collapse,
  frame regex (grammar-closed connectors) — caught ラグジュアリーな感じに with no wordlist entry
- Judge cards JA+EN final: 0-5 rubric, 10歳 bar, randomized uuid4 fence (no literal fences)
- Two-Parameter split: CountModelId (plain, CountTokens) / JudgeModelId (jp. profile, Converse)
- IAM: [CountTokens, InvokeModel] on 3 measured ARNs, zero wildcards, account ID via pseudo-param

## FACTS (probed live 2026-08-11/12)
- Haiku 4.5 Tokyo = INFERENCE_PROFILE only; jp. profile routes ap-northeast-1 + ap-northeast-3
- CountTokens rejects profile IDs ("doesn't support counting tokens"); Converse rejects plain IDs.
  Two doors, two keys — permanent
- No bedrock:Converse IAM action exists — Converse authorizes via InvokeModel
- system = top-level Converse param, never a message role (boto3 doc misleads)
- stopReason "max_tokens" = truncated JSON = our cap's fault, distinguished in JudgeOutputError
- Haiku wraps JSON in ```json fences despite instruction — strict-strip in parse (clean fence only)
- CloudFormation: defaults apply at parameter BIRTH; existing stacks reuse remembered values.
  Fix = explicit --parameter-overrides once

## DECISIONS
- Badge + meta.region = "jp" / 日本国内 (jp. profile serves Osaka too) — audit-round-3 erratum
- §8 amended: lints + lang added; unbuilt fields OMITTED not zeroed; §9 scale 0-5, gate ±1
- Fence-strip: cosmetic wrapper only; everything else still fails the contract loudly

## OPEN
- Cross-language comparability: JA input_data=1 vs EN=4 on twin prompts. Per-language gates
  passed; comparability ungated and visibly loose. Observation, not defect — revisit with JA test set
- Tailor (/rewrite): slipped BY PLAN — reuses judge plumbing. Next session's first build
- Client hoisting (boto3 per-call → module level), EN lint rulebook, tier-one 表記ゆれ
  normalization, SudachiPy 3-number measurement, envelope-vs-letter token display decision
- PLAN.md promotion of accumulated errata

## LESSONS (Day 3 scars, keep)
- 言葉は無限、文法は有限 — chase frames and connectors, never vocabulary
- Append needs a list that's already born; Python reads the left margin like music
- Compile at home before you ship the truck (py_compile = free; deploy = minutes)
- The stack remembers: defaults are for birthdays. The template proposes; samconfig disposes
- The meter and the engine take different keys
- あれ inside 可能であれば: substring ≠ word — boundaries are earned, not free
- A 502 that's polite, bilingual, and leak-free is the error handler WORKING — read the voice
  of an error before assuming crash

## NEXT — Day 4 (per plan: Doctrine Library)
- S3 Vectors Tokyo availability: verify LIVE first (§2a; fallback pgvector, 10-min decision)
- Embedding shootout: Titan V2 vs Cohere on JA doctrine queries
- KB + hierarchical chunking + language metadata + citations
- Warm-up quiz: the four blanks (env tag / card arg / stopReason / bounds) — cold, ownership debt
- Gate: JA user gets JA-sourced tips with working links
