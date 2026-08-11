# Haruka — BUILD_STATE
Date: 2026-08-11 · Day 2 (end)

## DONE
- S3 + CloudFront page LIVE (private bucket, OAC sigv4/always, RegionalDomainName,
  SourceArn-gated policy) — https://dddcab9qeo0cy.cloudfront.net
- FastAPI + Mangum swap (step ①): /hello parity proven by compact-JSON fingerprint
- CountTokens verified EMPIRICALLY for Haiku 4.5 on bedrock-runtime (Branch A):
  29 EN / 47 JA. §16 "newest model" risk row CLOSED
- Console tokenizer cross-check: JA exact, EN +1 (console-side wrapping; newline
  ruled out empirically). Count source of truth = CountTokens converse shape. Δ≤1 accepted
- sam build --use-container adopted (pydantic-core/tiktoken = compiled Rust; Mac arm64
  wheels die on x86_64 Lambda)

## FACTS (verified against live docs/console TODAY)
- Admin user = rira-admin (record corrected; ARN is the answer key)
- tiktoken 0.13.0 · fastapi 0.141.1 · mangum 0.21.0 · encoding o200k_base
- IAM ARN form: arn:aws:bedrock:ap-northeast-1::foundation-model/<id> (two colons, no acct)
- bedrock-mantle = REAL second Bedrock endpoint (OpenAI/Anthropic-native APIs).
  Irrelevant to Haruka (Branch A proven). Coach doubted it; live docs overruled coach.
- Bucket: haruka-sitebucket-n7eti47cklfq

## DECISIONS
- Validation errors: static bilingual (JA line + EN line), NO language detection in v1 —
  stacked can't misdetect. Detection idea → Day 3 judge heuristic, errors borrow later
- MemorySize: 512 (memory buys CPU; faster cold starts) — lands with step ④
- Privacy: override FastAPI's default 422 handler — Pydantic v2 echoes user text into
  error bodies. Static body, 400, log length+status only
- tiktoken: BUNDLE encoding into artifact (TIKTOKEN_CACHE_DIR=/var/task/tiktoken_cache);
  /tmp only fixes the crash, not the cold-start network fetch. Pin protects the cache hash

## LESSONS (Day 2 scars, keep)
- cd takes one path; angle brackets = fill me in; contracts aren't commands
  ("if it doesn't start with a program, the terminal doesn't want it")
- Redirect breaks the signature → 403 · Badge says CloudFront, Condition asks which ID ·
  Empty string = old key not used
- Empty bucket 403 == broken-OAC 403 — door, furniture, knock
- Break a copy to prove the DETECTOR sees; for WIRING, find the fingerprint
- The door says "message"; the kitchen says "detail"; the typewriter never lies
  (unrouted paths bounce off API Gateway — FastAPI never sees them)
- The letter weighs 5g; the envelope weighs 23 (converse wrapper overhead)
- Freshness clause cuts ALL directions: corrected AWS docs (Haiku 4.5), corrected Code's
  framing (/tmp), corrected the COACH (bedrock-mantle). Nobody's memory outranks live docs

## NEXT — Day 3 (slipped: /count steps ②–⑤)
- ② POST /count route + two stubs (Code scaffolds) → YOUR HANDS write both bodies:
  count_claude_tokens (boto3 count_tokens, converse, env JUDGE_MODEL_ID),
  count_gpt_tokens_est (tiktoken o200k_base)
- Check python3.12 bundled boto3 version supports count_tokens before writing stub 1
- ③ privacy-safe error handler · ④ SAM: /count event + JUDGE_MODEL_ID + least-priv
  bedrock:CountTokens + MemorySize 512 · ⑤ requirements + bundled encoding
- GATE (Day 2, carried): /count returns EN+JA counts matching CountTokens truth
- Then Day 3 proper: Judge + Tailor (original schedule pressure: watch the overrun rule)

## DONE (append)
- /count LIVE, gate GREEN: 29 EN / 47 JA — CLI, console, endpoint unanimous
- Least-priv bedrock:CountTokens on single model ARN PROVEN live (no 403) — UNVERIFIED flag resolved
- tiktoken o200k_base bundled + red-tested (network-blocked probe: cache works, fetch eliminated)
- JudgeModelId Parameter deduped (!Ref both places)

## FACTS (append)
- boto3 needs ≥ 1.40.14 (2025-08-20) for count_tokens; Lambda bundled version = probe-then-pin,
  doc no longer publishes a table

## OPEN QUESTION — tomorrow's first decision
- EN: claude_tokens 29 vs gpt_est 5 — envelope vs letter. Side-by-side is misleading as-is.
  Options: subtract measured envelope / show as-billed both / label the difference

## LESSONS (append)
- Code stays open until the block ends (two fresh-hire briefings tonight, ~5 min each)
- Two true numbers can still tell one lie
