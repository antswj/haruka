# Haruka — BUILD_STATE

Date: 2026-08-09 · Day 1

## DONE

- AWS account live: root MFA, rira-admin (MFA), budget alarm USD100

- Bedrock access confirmed via playground (Haiku replied)

## FACTS (verified against live console)

- Embeddings: amazon.titan-embed-text-v2:0

- Haiku ID: anthropic.claude-haiku-4-5-20251001-v1:0

- Cohere Embed ID (Day 4 challenger): <paste or "not listed in Tokyo">

## PLAN ERRATA (fold into v1.2.1)

- Model-access page RETIRED — serverless models auto-enable on first invoke; "approval delay" risk deleted; access control = pure IAM per model ARN

- Titan V2 is English-optimized per AWS → Day 4 gains a JA embed shootout: Titan vs Cohere on JA doctrine queries

## LESSONS (Day 1 scars, keep)
- Tabs are fatal in YAML — `cat -et` makes them visible
- The terminal runs text; files hold text — edits go through nano
- Colon marries, comma separates
- [brackets] in prompts = default; Enter accepts
- Gates catch lies: `git remote -v` caught an unpushed repo

## NEXT — Day 2
- Warm-up (slipped item): S3 + CloudFront static page
- /count endpoint: Bedrock CountTokens (Haiku) + tiktoken — both counts side by side, v1 hard requirement
- Doctrine doc lists FROZEN: JA-first + EN
- Gate: EN + JA counts match Bedrock console tokenizer; page loads over CloudFront
