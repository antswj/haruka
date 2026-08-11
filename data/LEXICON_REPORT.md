# Deliverable 2 — Existing downloadable Japanese lexicons

Survey of ready-made Japanese word dictionaries and lexicons that could be reused in Haruka's public MIT-licensed repo, for the four lint categories: vague/hedge words, クッション言葉, task verbs, output-format markers.

Researched 2026-08-11. Every license below was read from the actual LICENSE file or the resource's own terms page, not from memory or from secondary write-ups. Three license claims failed verification on a second pass and are corrected here — they are marked **CORRECTED**.

---

## The short version

**There is no downloadable クッション言葉 dataset. There is no 曖昧語辞書. There is no Japanese task-verb or output-format-marker lexicon.** Those three of the four lists have no prior art to adopt — they have to be authored. What does exist, and is genuinely worth taking, is (a) one strong hedge/modality dictionary, (b) an MIT-licensed textlint rule family that already implements part of this lint, and (c) orthographic normalization data so the matching does not break on 表記ゆれ.

---

## Tier 1 — take these

| Resource | License | Format / size | Why |
|---|---|---|---|
| **[Tsutsuji 日本語機能表現辞書「つつじ」](https://sites.google.com/edu.teu.ac.jp/cl-lab/cl-lab/%E7%A0%94%E7%A9%B6/%E8%A8%80%E8%AA%9E%E8%B3%87%E6%BA%90)** (Tokyo Univ. of Technology, Matsuyoshi) | **CC BY-SA 4.0** — changed from CC BY-SA 3.0 on 2023-11-03 | ZIP of structured dictionary text (`tsutsuji-1.1u.zip`), ~1.2 MB; **16,801 entries** at surface level (L9) | The single best-fitting existing resource for the vague/hedge list. Hierarchical over 9 abstraction levels, so 〜かもしれない / 〜のではないか / 〜と思われる / 〜ようだ collapse to one canonical hedge class. **ShareAlike** — keep derived data in its own directory under CC BY-SA 4.0 with attribution; your code stays MIT. |
| **[textlint-ja rule family](https://github.com/textlint-ja)** — `ja-no-weak-phrase`, `ja-no-redundant-expression`, `preset-ai-writing`, `ja-no-abusage`, `morpheme-match`, `preset-ja-technical-writing` | **MIT** throughout (© azu) | npm packages; patterns in JS/TS source, plus a `dict/prh.yml` in `ja-no-abusage` | Closest prior art to a Japanese prompt lint, and free of data-license entanglement. `preset-ai-writing` (5 rules, ~1.1k stars) specifically targets LLM-generated Japanese. `morpheme-match` is the right engine for POS-aware matching — so 要約 as a bare noun does not fire, only サ変動詞 usage. |
| **[SudachiDict](https://github.com/WorksApplications/SudachiDict)** + its [synonym dictionary](https://github.com/WorksApplications/SudachiDict/blob/develop/docs/synonyms.md) + [chikkarpy](https://github.com/WorksApplications/chikkarpy) | **Apache 2.0** (LEGAL file: small_lex from UniDic BSD, core_lex from NEologd) | CSV lexicon / compiled `.dic`; small 668,650 · core 1,285,798 · full 2,909,482 entries. Synonyms are RFC-4180 CSV, 11 columns | Carries **normalized forms (正規化表記)** that collapse 表記ゆれ — サーバ/サーバー, 打ち合わせ/打合せ. This is load-bearing: cushion words alone showed nine attested orthographic pairs. The synonym dictionary's 表記ゆれ and abbreviation columns give you canonical keys, and its expansion-control flag stops over-expansion. |
| **[SNOW T15 やさしい日本語コーパス](https://www.jnlp.org/GengoHouse/snow/t15)** | **CC BY 4.0** — no ShareAlike | XLSX, 3.5 MB, **50,000** aligned EN / standard-JA / simplified-JA triples | The most permissively licensed substantial Japanese paraphrase resource found. The standard→simplified alignment is effectively a verbose-to-plain rewrite table, minable for the rewrite suggestions Haruka shows next to a flagged prompt. |

Also MIT and drop-in: **[stopwords-iso/stopwords-ja](https://github.com/stopwords-iso/stopwords-ja)** (JSON + plain text) — the practical replacement for the SlothLib list, which is dead (see below).

---

## Tier 2 — usable with conditions

| Resource | License | Condition |
|---|---|---|
| **[Japanese WordNet (wn-ja)](https://bond-lab.github.io/wnja/jpn/downloads.html)** — 57,238 synsets, 93,834 JA words, SQLite3/XML/TSV | NICT BSD-style, commercial use royalty-free | Copyright notice on **all** copies of software, database and documentation; NICT's name may not be used for publicity; attribution link required. If you use the English side too, Princeton WordNet's license also applies. |
| **[JMdict / EDICT](https://www.edrdg.org/wiki/index.php/JMdict-EDICT_Dictionary_Project)** — 200k+ entries, XML/text | CC BY-SA 4.0 | ShareAlike on derived data; acknowledgement required in docs, publicity **and on-screen**; deployed apps expected to track current versions. Only marginally useful here (register markers). |
| **[JTF日本語標準スタイルガイド](https://www.jtf.jp/tips/styleguide)** — v4.0, released 2026-07-25 | **CC BY 4.0** | **CORRECTED:** the loosening to CC BY happened *at v3.0*, not at v4.0 — the JTF page states 「第3.0版からクリエイティブ・コモンズ・ライセンスが『表示』（CC BY 4.0）に変更されました」. v3.0 was already CC BY 4.0. The pre-3.0 license is not named on the page, so do not assert it was CC BY-SA. Note separately that `textlint-rule-preset-JTF-style` still carries a 「JTF日本語標準スタイルガイド2.0 (JTF, CC BY-SA)」 derivation notice that must be preserved if you vendor that preset. It is prose, not a dataset — rules must be transcribed by hand. |
| **[UniDic](https://clrd.ninjal.ac.jp/unidic/)** — unidic-cwj / unidic-csj, latest 202512 (2025-12-31) | **CORRECTED: modern UniDic is TRIPLE-licensed GPL v2.0 / LGPL v2.1 / modified BSD — there is no CC option offered for it.** The earlier "dual-licensed, choose CC or free" reading was wrong: the choice is *within* the triple license. | Elect **modified BSD** to stay MIT-compatible; retain the copyright notice and ship AUTHORS/LICENSE. Publications must state the version used. **Separately: every classical/historical variant** (上代語, 中古和文, 中世口語/文語, 近世文語, 近世江戸/上方口語, 近代文語, 旧仮名口語, 和歌, 関西方言…) is **CC BY-NC-SA only** — avoid entirely. `unidic-csj` (spoken) is the better base if you want spoken-register filler coverage. |
| **[mecab-ipadic-NEologd](https://github.com/neologd/mecab-ipadic-neologd)** — ~3.2M surface/reading pairs | Apache 2.0 (verified from COPYING) + upstream data attributions | **CORRECTED: the repo is NOT archived** — no archive banner. But it is not maintained either: latest release is **v0.0.7, 2020-08-20**, README copyright reads 2015-2019, and the README still advertises Monday/Thursday updates that stopped happening. Legally fine, practically stale, and largely irrelevant to hedge/politeness detection. **Use SudachiDict instead** — its LEGAL file confirms core_lex already derives from NEologd under Apache 2.0. |
| **[IPADIC / mecab-ipadic](https://github.com/taku910/mecab/blob/master/mecab-ipadic/COPYING)** | NAIST BSD-style permissive, commercial use allowed | Must reproduce the NAIST notice and full license paragraphs in any copy. Frozen since ~2007. |
| **[JUMAN++](https://nlp.ist.i.kyoto-u.ac.jp/?JUMAN)** | Apache 2.0 (verified from the official manual PDF — the lab wiki does not restate it) | NOTICE retention. |
| **[Zunda 日本語拡張モダリティ解析器](https://github.com/jmizuno/zunda)** | Modified BSD; bundled CDB++, liblinear, TinyXML-2 have their own | This is the linguistic layer *under* hedging — it labels each predicate for factuality, information source, judgement. Check `dic/` provenance separately; the modality dictionaries may derive from annotated corpora with their own terms. |
| **[日本語評価極性辞書 (Tohoku, 乾・岡崎研)](https://www.cl.ecei.tohoku.ac.jp/Open_Resources-Japanese_Sentiment_Polarity_Dictionary.html)** — ~5,000 用言 + ~8,500 名詞 | No license name. Page says commercial use OK with credit: 「クレジットを明記していただければ，商用利用も可能です」 | **Redistribution is never addressed.** Download at build time rather than vendoring, or email the lab first. Sentiment only — no hedge or politeness dimension, so its value here is indirect anyway. |
| **[KNB Corpus](https://nlp.ist.i.kyoto-u.ac.jp/kuntt/)** — 4,186 sentences with 意見・評価タグ | Reported BSD 3-clause — **but only by a third-party catalogue.** The official Kyoto page states no terms at all. | Read the tarball's bundled license before relying on it. The opinion/evaluation tags are closer to the subjectivity axis than any polarity lexicon. |
| **[genshijin](https://github.com/interfacex-co-jp/genshijin)** | MIT | Closest existing work to this exact problem — an agent skill that compresses verbose Japanese ~75%, explicitly targeting 敬語・丁寧語, クッション言葉, 前置き表現, ぼかし. But it ships **no dictionary file**: the rules are prose in `SKILL.md`. You extract a seed list, you don't reuse data. |

---

## Tier 3 — not usable

| Resource | Blocker |
|---|---|
| **[日本語評価極性辞書 (Takamura, 東工大)](http://www.lr.pi.titech.ac.jp/~takamura/pndic_ja.html)** | Redistribution **explicitly prohibited**: 「再配布は禁止させていただきます」. Research use only. Worth knowing: this is the most-cited Japanese sentiment lexicon in blog tutorials, so a lot of downstream projects are quietly non-compliant. |
| **[JIWC-Dictionary](https://github.com/sociocom/JIWC-Dictionary)** (NAIST) | **No LICENSE file exists** — verified, no file, no badge, no README statement. Default copyright, all rights reserved. |
| **[pymlask / ML-Ask](https://github.com/ikegami-yukino/pymlask)** | BSD-3 covers the Python wrapper only. The bundled emotion data traces to Nakamura (1993) 感情表現辞典 and a Gakken 2017 dictionary — commercially published works with no grant of redistribution. |
| **[WRIME](https://github.com/ids-cv/wrime)** | CC BY-**NC-ND** 4.0. NC blocks commercial use; ND blocks deriving a wordlist. |
| **[日本語話し言葉コーパス (CSJ)](https://clrd.ninjal.ac.jp/csj/fee.html)** | Paid, application-gated, per-seat: ¥25,000 (students) → ¥10,000,000 (commercial). The ideal empirical filler source, and completely closed. |
| **[BCCWJ](https://clrd.ninjal.ac.jp/bccwj/)** and **[CEJC](https://www2.ninjal.ac.jp/conversation/cejc.html)** | Contract-gated, no redistributable download. |
| **[BCCWJ 語彙表](https://clrd.ninjal.ac.jp/bccwj/freq-list.html)** | Free to download — but research/education purpose only. Use privately to calibrate frequency thresholds; do not ship. |
| **[名大会話コーパス (NUCC)](https://mmsrv.ninjal.ac.jp/nucc/)** | CC BY-**NC-ND** 4.0. Free to download, 129 conversations / ~100 hours of natural casual Japanese — and the ND clause forbids deriving a wordlist from it. The most frustrating entry on this list. |
| **[SlothLib 日本語ストップワード](http://svn.sourceforge.jp/svnroot/slothlib/CSharp/Version1/SlothLib/NLP/Filter/StopWord/word/Japanese.txt)** | **Dead source.** svn.sourceforge.jp times out; osdn.net fails DNS entirely. The ~310-word list survives only in third-party gists of unknown provenance. Use stopwords-iso instead. |
| **[chakoshi](https://chakoshi.ntt.com/)** (NTT Com) | SaaS guardrail API. No lexicon published. |
| **[京都大学テキストコーパス](https://nlp.ist.i.kyoto-u.ac.jp/)** | Annotations only; underlying 毎日新聞 text must be licensed separately. Terms could not be verified — the lab's page would not render. |

Off-topic but useful as structural prior art, both MIT/Apache: **[inappropriate-words-ja](https://github.com/MosasoM/inappropriate-words-ja)** (MIT — good template for versioning a Japanese wordlist repo) and **[japanese-toxic-dataset](https://github.com/inspection-ai/japanese-toxic-dataset)** (Apache 2.0).

---

## The license trap worth naming

Three of the four Japanese sentiment tools surveyed demonstrate the same pattern: **an MIT or BSD badge on the repo, unlicensed third-party dictionary data vendored inside it.** `oseti` is MIT with the Tohoku dictionaries bundled and no data license stated. `pymlask` is BSD-3 with data from two commercially published dictionaries. `textlint-rule-preset-JTF-style` is MIT code carrying a CC BY-SA derivation notice.

A GitHub license badge does not relicense bundled data. If Haruka vendors anything, the check is what the *upstream data* says, not what the wrapper repo's LICENSE file says.

---

## What could not be verified

- Exact hedge-phrase list inside `textlint-rule-ja-no-weak-phrase` — raw.githubusercontent 404'd on path guesses, unpkg and jsdelivr blocked by proxy. Read `src/` from a clone.
- Total group count of Sudachi `synonyms.txt` — fetch truncated at group 000284; docs do not state a total.
- KNB corpus license at source (see above).
- GitHub commit metadata generally — API returns 403 here and `/commits/` is robots-disallowed, so repo activity was established from committed files and release pages rather than commit dates.
- Exact byte sizes for most UniDic and Japanese WordNet downloads.

---

## Sources

All URLs above were fetched. License-critical pages additionally re-verified on a second independent pass 2026-08-11: [JTF styleguide](https://www.jtf.jp/tips/styleguide), [UniDic FAQ](https://clrd.ninjal.ac.jp/unidic/faq.html), [Takamura pndic](http://www.lr.pi.titech.ac.jp/~takamura/pndic_ja.html), [JIWC](https://github.com/sociocom/JIWC-Dictionary), [Tsutsuji](https://sites.google.com/edu.teu.ac.jp/cl-lab), [SNOW T15](https://www.jnlp.org/GengoHouse/snow/t15), [textlint preset-ai-writing](https://github.com/textlint-ja/textlint-rule-preset-ai-writing), [NEologd COPYING](https://raw.githubusercontent.com/neologd/mecab-ipadic-neologd/master/COPYING), [SudachiDict LEGAL](https://raw.githubusercontent.com/WorksApplications/SudachiDict/develop/LEGAL).
