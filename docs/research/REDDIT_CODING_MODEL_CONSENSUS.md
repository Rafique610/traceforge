# Developer sentiment on coding LLMs and Ollama Cloud (Reddit research attempt)

Date of research: 2026-11-21. Method: WebSearch and WebFetch only. No Ollama API calls, repo not read.

## 0. Headline limitation: Reddit was not accessible

- WebSearch with `allowed_domains: reddit.com` returned HTTP 400 ("domain not accessible to our user agent").
- `site:reddit.com` queries returned zero Reddit URLs (3 queries tried).
- WebFetch on www.reddit.com is blocked by the tool ("unable to fetch from www.reddit.com").
- **Result: ZERO Reddit threads were read, and zero Reddit posts were seen even as snippets.** No Reddit URLs, subreddit names, dates or quotes are cited below, because none were found.
- Every Reddit data point asked for (r/ollama, r/LocalLLaMA, r/ClaudeAI, etc.): **not found**.
- The only Reddit-adjacent evidence is secondhand. A dev.to article says it draws on "Reddit threads", but it names none, so it cannot be verified.
- The substitute sources are Hacker News (via a mirror), dev blogs and vendor pages. This is NOT a Reddit consensus. Treat everything below as a proxy.

## 1. Source log

Legend: "Read" = full page fetched via WebFetch (an internal summarizer produced the extract, so quotes are secondhand). "Snippet" = search-result summary only.

| # | URL | Community / type | Date | What it says | First-hand? | Read? |
|---|---|---|---|---|---|---|
| 1 | https://hn.svelte.dev/item/47993235 (mirror of an HN thread on the thinkpol.ca article "Kimi K2.6 just beat Claude, GPT-5.5, and Gemini in a coding challenge") | Hacker News | ~2026-04-30 (inferred from the article URL; mirror shows "6 months ago") | Multiple commenters call Kimi K2.6 good value and a daily driver. One says it outperformed Sonnet on a C/Python project. Another says it has "a high ceiling but... a low floor". Others say it is slow and verbose, loops, and breaks heredoc shell edits. One says it "can get into all kinds of issues (loops and such)" and needs a good harness. DeepSeek V4 Pro is described as "close to Opus" for general work but weak at the Blender API. GLM "crapped the bed once or twice"; another prefers GLM 5.1 for long complex reads. Flash models (Qwen, DeepSeek) are suggested for tool calling under a stronger planner. One user moved from Claude Pro to Kimi via Ollama Cloud at $20/mo and "rarely hits limits"; another says Ollama has "reliability issues but for the price it's worth it". | Mostly first-hand user anecdotes, several users. Some is hearsay. | Read (full) |
| 2 | https://dev.to/danishashko/the-best-llms-for-agentic-coding-in-2026-real-world-not-just-benchmarks-96n | dev.to blog | 2026-05-07 | Recommends Claude Opus 4.7 / Sonnet 4.6 and GPT-5.5 as top. Open-weight picks are Kimi K2.6 (long-horizon), DeepSeek V4-Flash (cheap routine edits) and Qwen3-Coder (cheap, self-host). Notes that Claude beats Kimi K2.6 on careful long-context work. Warns SWE-bench may be contaminated and that the harness swings results 30-50 points. Mentions Opus 4.6 over-scoped edits. | Author claims personal experience, but it leans on vendor benchmarks. Mixed. | Read (full) |
| 3 | https://dev.to/amareswer/ollama-cloud-free-vs-pro-usage-limits-pricing-what-you-actually-get-2026-3ieo | dev.to blog | 2026-06-11 | Free tier: "base quota", limited concurrency, GPU-time metering, 5-hour session and 7-day weekly resets. Advises Free users to stick to level 1-2 models (gpt-oss:20b is level 1, deepseek-v4-pro level 4). Pro $20/mo, about 50x Free. No Devstral mention. A reader comment claims a later pricing change (Pro = $60 usage), unverified. The page has a leftover "CHECK exact number" HTML note. | Secondhand explainer. | Read (full) |
| 4 | https://dev.to/insight105/run-frontier-ai-for-free-ollama-cloud-models-with-opencode-4j54 and others from search (a May 2026 dev.to guide) | dev.to | 2026-05 (per search summary) | Says GLM-4.7 and GPT-OSS 20B worked without Pro. Says Kimi K2.6 and GLM-5.1 return 403 without Pro. The summary does not make clear whether this is the same page as #3. | Unclear. | Snippet only |
| 5 | https://www.ayautomate.com/free-models/ollama-cloud-kimi-k2-6 | Directory/promo site | undated | Lists Kimi K2.6 as "Free tier". Contradicts #4. Likely low-quality directory. | Promo/hearsay | Snippet only |
| 6 | https://hashnode.com/blog/free-open-weight-model-apis | Hashnode | undated | Claims Ollama cloud bills per token. Conflicts with the GPU-time metering in #3 and #1. | Hearsay | Snippet only |
| 7 | https://hn.nuxt.dev/item/45601834 and https://hn.nuxt.dev/item/46845845 (HN mirrors) | Hacker News | probably late 2025 and early 2026 (unverified) | Commenter: GLM-4.6 with Charm Crush "absolutely incredible, especially with high thinking". Another: GLM "good for the low hanging fruit and planning". | First-hand anecdotes | Snippet only |
| 8 | https://forum.langchain.com/t/harmony-response-format-sometimes-outputted-when-using-gpt-oss-120b-as-an-agent/2554 ; https://forums.developer.nvidia.com/t/dgx-spark-gpt-oss-120b-runtime-with-reliable-tools-strict-support-for-roo-code/355686 ; https://community.oracle.com/CustomerConnect/discussion/962032/gpt-oss-120b-model-unable-to-call-document-tools-in-ai-agent-framework ; https://huggingface.co/openai/gpt-oss-120b/discussions/151 | Vendor forums / HF discussions | undated (2025-2026) | gpt-oss-120b tool calling is stack-sensitive. Harmony format leaks into agent output. A runtime commit broke parallel tool calls. One Oracle user saw it fail to call tools while GPT-5 Mini worked. NVIDIA user got reliable tools in Roo Code with the right vLLM build. | First-hand bug reports | Snippet only |
| 9 | https://akitaonrails.com/en/2026/06/14/llm-benchmark-kimi-2-7-code-glm-5-2-minimax-m3-local/ and its 2026/04/24 sibling | Personal blog (benchmark of Kimi K2.7 Code, GLM 5.2, MiniMax M3) | 2026-06-14 / 2026-04-24 | Found in search titles only. The fetch returned 404, so content unknown. | n/a | Not read; content not found |
| 10 | https://dev.to/hassann/minimax-m3-vs-deepseek-v4-pro-vs-qwen-37-best-open-weight-coding-model-in-2026-49id ; https://dev.to/zyvop/the-best-open-source-llms-for-coding-right-now-june-2026-n10 ; https://botmonster.com/ai/chinese-open-weight-coding-stack-2026/ ; https://pasqualepillitteri.it/en/news/16873/best-chinese-ai-coding-models-2026 | Blogs / listicles | 2026-06 to 2026-09 | Search summary: DeepSeek V4-Pro is the most consistent pick across sources. GLM-5.2 is said to be best for long-horizon debugging. MiniMax M3 numbers are vendor-reported. Kimi K3 is topped in a Sept 2026 ranking. OpenRouter real-usage ranks MiMo V2.5, MiniMax M3 and Tencent Hy3 first. Closed models (Claude, GPT) are still stronger overall. | Listicles, mostly vendor benchmarks | Snippet only |
| 11 | https://registry.ollama.ai/blog/coding-models ; https://docs.ollama.com/cloud ; https://ollama.com/pricing | Ollama official | various | Official statements about the cloud. Not developer sentiment. | Vendor | Snippet only |

## 2. Synthesis (proxy sources, not Reddit)

### Models mentioned positively by more than one independent source

- **Kimi K2.6**:
  - HN has several users calling it good value and a daily driver, and the dev.to article lists it as the open-weight long-horizon pick.
  - It is also the one named most often in connection with Ollama Cloud.
  - Confidence: moderate.
- **DeepSeek V4-Pro / V4-Flash**:
  - Listicles are consistent on V4-Pro.
  - HN says "close to Opus" for general work.
  - The Flash variants are suggested for cheap tool-calling and routine edits.
  - Confidence: low-moderate. Only one first-hand HN voice and the rest is listicles.
- **GLM (4.6 / 5.1 / 5.2)**: praised for planning, long complex reads and debugging in several places, but one commenter reports unreliability. Confidence: low-moderate.

### Isolated opinions (single source only)

- Qwen3-Coder as the cheapest credible option (#2 only).
- MiniMax M3 (vendor-reported numbers; no first-hand experience found).
- Kimi K3 topping a ranking (one listicle).
- Not found at all: any user report on kimi-k2.7-code, kimi-k3.1-pro, glm-5.3, glm-5.3-flash, deepseek-v4.1-flash, minimax-m3.1-flash, nemotron-3-ultra, nemotron-3-super, gemma4:31b, mistral-large-4, mimo-v2.6, muse-spark-open, inkling-2-small, beam, or Devstral 2. I did not run targeted searches for each of these because the Reddit channel was blocked and general searches surfaced nothing on them.

### Overrated or questioned

- Single-run benchmark wins (e.g. "Kimi K2.6 beat Claude") are widely doubted by HN commenters.
- SWE-bench Verified may be contaminated, and independent runs are reportedly 4-8 points lower than vendor claims (#2).
- Kimi K2.6 is characterized as "high ceiling, low floor" (#1).
- Gemini 3.1 Pro has an anecdotal "way worse than Opus/GPT-5.5" comment, which is out of scope for Ollama Cloud.

### Best for agentic coding

- Closed models (Claude Opus/Sonnet, GPT-5.x) are repeatedly said to remain better.
- Among open models, the candidates are Kimi K2.6, GLM-5.x, DeepSeek V4-Pro.
- Several HN commenters stress that the harness (OpenCode, Pi, Crush, Cline/Roo) matters as much as the model.

### Debugging vs generating

- No source cleanly separated the two. The dev.to piece suggests thinking-mode models for hard bugs and cheaper ones for boilerplate. One listicle says GLM-5.2 is good for long-horizon debugging (snippet only).
- Minimal-patch generation specifically: not found. The only adjacent evidence is that Opus 4.6 over-scoped edits (#2), and one HN user says Kimi "never did anything other than what was asked" (#1), which is contradictory evidence on over-editing.

### Reported problems

- **Tool-call failures:** gpt-oss-120b is highly serving-stack-sensitive (#8). Kimi breaks heredoc edits (#1). Harmony-format leakage was reported with gpt-oss.
- **Looping:** Kimi K2.6 (#1, one or two commenters).
- **Verbosity, slowness and cost on long tasks:** Kimi K2.6 (#1). One user reports $2.25 vs $0.20 for the same task.
- **Hallucinated APIs:** DeepSeek V4 Pro was weak at the Blender API (#1, one comment). Little else found.
- **Over-editing:** only the Opus 4.6 mention.

### Ollama Cloud free tier (may be outdated)

- Agreed across #3 and #1: usage is metered by GPU time, not tokens. Limits are session (5h) and weekly (7d) windows. Exact numbers are unpublished.
- Free is "light usage" with limited concurrency (1 concurrent model per one snippet; #3 says "limited"). Pro is $20/mo with roughly 50x quota and 3 concurrent models.
- Which models are free is disputed. #4 says heavy models (Kimi K2.6, GLM-5.1) are Pro-only and light ones (gpt-oss:20b, GLM-4.7) work free. #5 says Kimi K2.6 is free. #3 says Free users should stick to levels 1-2 (gpt-oss:20b level 1, deepseek-v4-pro level 4).
- One HN user reports rarely hitting limits on Pro with Kimi, but "reliability issues".
- Devstral: no source in my results mentions its retirement. Per the brief it retired on Ollama Cloud on 2026-07-15. Sources dated before that (#3 on 2026-06-11, #2, #4) cannot reflect it and are possibly stale. I could not confirm the retirement independently.
- The most recent dated sources I found are June 2026, so nothing here covers Aug-Nov 2026 limit or pricing changes. A reader comment on #3 hints at one.

## 3. Confidence and limitations

- Overall confidence that this reflects Reddit consensus: **very low (effectively none)**. Zero Reddit data was obtained.
- Confidence in the proxy findings: low to moderate. Sample is tiny: one fully read HN thread, two fully read dev.to posts, and snippet-level summaries for the rest.
- Search-engine bias: the results are skewed to SEO listicles, which often rely on vendor benchmarks. Search summaries were produced by a model and could be lossy.
- Fetched pages were summarized by a small model, so quotes are secondhand and not verbatim-checked.
- Model names from the account list (kimi-k3.1-pro, glm-5.3, etc.) turned up little or nothing, so no claims are made on them.
- To close the gap, someone with Reddit access should search r/ollama, r/LocalLLaMA, r/LocalLLM, r/ClaudeAI and r/cursor manually (or use Reddit's official API) for the model names above.
