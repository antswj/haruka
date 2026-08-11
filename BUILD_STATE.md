# Haruka — BUILD_STATE
Date: 2026-08-11 · Day 2 (mid-day — block 1 complete, block 2 pending)

## DONE
- [Day 1 slip cleared] S3 + CloudFront static page LIVE over HTTPS
  - Private bucket (all public-access blocks on), no website hosting
  - OAC (sigv4/always), RegionalDomainName origin, SourceArn-gated bucket policy
  - CachingOptimized managed policy + Compress
  - URL: https://dddcab9qeo0cy.cloudfront.net
- sam validate --lint clean (SAM CLI 1.165.0); linter proven live by breaking a copy first
- Committed + pushed: template.yaml, frontend/index.html

## FACTS (verified against live docs/console)
- Admin IAM user = rira-admin (prior record said anthony-admin — CORRECTED, ARN is the answer key)
- CountTokens API: real, zero-cost, Tokyo-supported; boto3 bedrock-runtime count_tokens;
  IAM action bedrock:CountTokens
- CountTokens docs list models only up to Sonnet 4 — Haiku 4.5 coverage UNVERIFIED,
  empirical test = first move of block 2 (PLAN §16 risk row; fallback: labeled approximation)
- Bucket: haruka-sitebucket-n7eti47cklfq

## PLAN ERRATA
- (none new today)

## LESSONS (Day 2 scars, keep)
- cd takes one path — it doesn't chain commands
- Angle brackets = fill me in, never literal (zsh reads < as a redirect)
- Redirect breaks the signature → 403 (global endpoint 307 vs RegionalDomainName)
- Badge says CloudFront; Condition asks which ID (confused deputy / SourceArn)
- Empty string = old key not used (legacy OAI field, schema-required, wired to nothing)
- Break a copy to prove the linter sees — green means nothing until you've seen red
- Empty bucket 403 looks identical to broken OAC — door first, furniture second, then knock
- Forward flag: React swap needs CustomErrorResponses 403→/index.html for deep links (Day 6)

## NEXT — Day 2, block 2
- Empirical test: count_tokens vs anthropic.claude-haiku-4-5-20251001-v1:0 (one CLI call)
- POST /count: CountTokens (exact) + tiktoken (labeled estimate) side by side
- Doctrine doc lists FROZEN: JA-first + EN (not yet done)
- GATE (open): EN + JA counts match Bedrock console tokenizer
