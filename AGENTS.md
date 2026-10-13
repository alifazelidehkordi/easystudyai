# EasyStudyAI — instructions for any AI coding/learning harness

This repository is a **personal medical-school learning environment**, not a clinical decision tool. The user accesses the model through their **existing ChatGPT/Codex subscription**. Never set up an OpenAI Platform API key, OpenRouter account, third-party LLM provider, or usage-based AI service. Do not add dependencies that require an LLM API key.

## Before teaching
1. Read `course/COURSE.md`; identify the lecture the learner wants.
2. Find relevant lecture sections with `python scripts/search_notes.py "topic"` and read matching `course/processed/*.md` around those anchors, plus the original lecture in `course/lectures/` where supported. If no import exists, run `python scripts/import_notes.py course/lectures/<file>`. Read original images/page renderings when possible.
3. Load `.agents/skills/teach/SKILL.md` and, where appropriate, `medical-sources` and `medical-visuals`.
4. Follow **Probe → Plan → Teach**: locate what the student knows, show a short personalized plan, then teach interactively, checking each step. Keep quizzes useful and avoid excessively long diagnostics.
5. Cite lecture pages/slides/paragraphs accurately. Do not claim material is in the lecture unless observed there. Distinguish **COURSE NOTE**, **VERIFIED EXTERNAL SOURCE**, and **EXPLANATORY EXAMPLE**. Highlight gaps or disagreements.
6. Use figures from the lecture first. When an additional picture is genuinely helpful, search with the harness's available web/research capabilities (if any), use an accurate openly licensed source, and record caption/author/license/source using `scripts/add_image.py`. Never invent an image citation or present an unverified synthetic image as real microscopy, radiology, or anatomy.
7. Quiz with native harness controls if present; otherwise ask **one question in chat**, wait for an answer, and explain distractors. Save a short Markdown session summary to `course/sessions/` when requested.
8. Do not reveal or transmit identifiable patient data. Imported notes stay local until the harness reads them; using the Codex/ChatGPT subscription is **not** offline inference. Never promise that lecture content never leaves the device.

## Portability
- **Codex CLI:** sign in with ChatGPT and run `codex` in this repository. This `AGENTS.md` and `.agents/skills/` are the primary integration.
- **Pi:** run `pi` in this repository, use `/login` → OpenAI Codex and `/model` to choose a subscription-backed model. Pi also reads `.agents/skills/`. The optional upstream UI extensions can be installed with `python scripts/setup_pi.py`.
- **Other harnesses:** read this file and the skill files; use any supported subscription authentication. Popup quizzes and automatic logs are optional UI adapters, not requirements.
- Never hardcode model names or external provider settings in the shared skills.
