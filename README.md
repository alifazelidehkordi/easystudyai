# EasyStudyAI

**A lightweight, notes-first AI tutor for medical school.** Inspired by the workflow in [amosblomqvist/learn](https://github.com/amosblomqvist/learn), but with anatomy, physiology, histology, pathology and professor lectures at its center.

- **No additional paid AI API or API keys.** Use the ChatGPT/Codex subscription login in Pi or Codex CLI. Subscription usage limits apply.
- **Portable.** `AGENTS.md` plus `.agents/skills/` works without a custom backend. Both Pi and Codex can discover these skills; other harnesses can read the same files.
- **Professor notes first.** Local PDF, PowerPoint, Word and text import, with page/slide references and saved embedded figures.
- **Probe → Plan → Teach.** One concept at a time, interactive recall and clinically relevant explanations, with source labels.
- **Visual learning.** Original lecture figures first; then attributed medical images gathered using whatever browsing/research functionality your harness already supports. The local `add_image.py` utility does **not** call any API.
- **Optional Pi UI.** Interactive quizzes and Obsidian-style session log extension from the *original* repository, fetched explicitly by the user, not bundled or hardwired.

## Quick start: Codex CLI (simplest)

Install [Codex CLI](https://github.com/openai/codex) using its official instructions. Then:

```bash
git clone https://github.com/alifazelidehkordi/easystudyai.git
cd easystudyai
python -m pip install -r requirements.txt   # optional: only needed for PDF/PPTX/DOCX imports
codex
```

At first login choose **Sign in with ChatGPT** (not an API key). In Codex, ask:

> Read AGENTS.md and course/COURSE.md. My topic is cardiovascular physiology. Follow Probe → Plan → Teach, grounded in my professor's imported lecture.

No separate AI API key, hosted application, or configuration server is required.

## Alternative: Pi + your Codex subscription

Install [Pi](https://pi.dev/docs/latest/quickstart) and start it inside this repo:

```bash
cd easystudyai
pi
```

In Pi, run `/login`, choose **OpenAI Codex**, then select an available subscription-backed model with `/model`. Pi automatically discovers the skills in `.agents/skills/`. This base mode works even without the original project's extensions; quizzes happen as normal chat questions.

To get the **original video-style quiz popup and Markdown/Obsidian log**, run this optional setup command **before** starting Pi (requires Git and internet):

```bash
python scripts/setup_pi.py --fetch
pi
```

Then inside Pi: `/md-log course/sessions/cardiac-cycle.md`. The setup copies only `quiz.ts`, `ask-user-question.ts` and `md-log.ts` from the user's upstream clone into the locally ignored `.pi/extensions/` directory; it does not add pinned Anthropic/OpenRouter subagents or model API integrations. To install from a manually downloaded upstream checkout instead: `python scripts/setup_pi.py --source /path/to/learn`.

The original project's code is **not vendored** here (check its rights/terms). Popup functionality depends on the installed Pi version; if unavailable, use chat quizzes and Markdown files without changing the learning logic.

## Import a professor's lecture

Put a lecture into the **ignored** `course/lectures/` directory (create it if necessary) and customize `course/COURSE.md`.

```bash
mkdir -p course/lectures
python scripts/import_notes.py "course/lectures/My lecture.pdf" --render-pages
# or
python scripts/import_notes.py "course/lectures/My slides.pptx"
python scripts/import_notes.py "course/lectures/My handout.docx"
```

The importer writes `course/processed/my-lecture-pdf.md` or similarly named output, with human-readable page/slide markers. Search across your imported lecture sections locally with `python scripts/search_notes.py "renal blood flow"`. PDF page snapshots and embedded figures are saved next to processed notes under `assets/`. **No OCR is performed**; scanned pages, charts, labels and complex document layouts need careful review against originals. All conversion is local; no model API calls.

Prompt your tutor:

> Read course/COURSE.md and the imported lecture on renal physiology. Map what my professor expects, ask a few diagnostic questions, show me the plan and wait for approval. Teach with diagrams and figure citations. Flag anything you add from outside the lecture.

## Add medical images (no search API required)

The tutor can use its existing web tools, when available, to **find candidate images**. Only choose an image after checking anatomical accuracy, attribution, usage rights, and privacy. Download it to your computer with the appropriate permission, then record the source locally:

```bash
python scripts/add_image.py \
  --file /path/to/approved-image.png \
  --title "Renal corpuscle histology" \
  --source-url "https://example.org/original-image-page" \
  --creator "Photographer or organization" \
  --license "CC BY 4.0"
```

The script copies the picture to `course/visuals/`, writes a metadata JSON file and maintains `ATTRIBUTIONS.md`. It explicitly marks pictures **unverified** until human review. Do not use the example URL as a real attribution. Original lecture figures and Mermaid diagrams require no external search.

## Project files

```text
AGENTS.md                        Instructions shared by harnesses
.agents/skills/teach/SKILL.md    Probe → Plan → Teach
.agents/skills/medical-sources/  Lecture-based citation and evidence rules
.agents/skills/medical-visuals/  Image selection, accuracy and attribution rules
course/COURSE.md                 Your syllabus and learning preferences
course/lectures/                 Your original lectures (gitignored)
course/processed/                Searchable imported notes (gitignored)
course/visuals/                  Medical image library (gitignored)
course/sessions/                 Lesson logs (gitignored)
scripts/import_notes.py          Offline lecture converter
scripts/add_image.py             Offline image/citation library helper
scripts/setup_pi.py              Optional import of upstream Pi UI extensions
```

## Checks

```bash
python -m unittest discover -s tests -v
```

The tests do not need API keys; PDF and slides tests run when the optional document dependencies are installed.

## Important limits

This is an **initial working foundation**, not a validated clinical education platform. Images and external claims are not medically certified by software. No automatic spaced-repetition scheduler, built-in web scraper or OCR is included yet. The original professor files stay on your machine; however, the **text/images the AI reads may be sent to the subscribed Codex/ChatGPT service**. Do not include identifiable real patient data. Course content is not clinical advice.

Reference documentation: [Pi skills](https://pi.dev/docs/latest/skills) · [Pi authentication](https://pi.dev/docs/latest/models) · [Codex](https://github.com/openai/codex) · [Original teaching system](https://github.com/amosblomqvist/learn).
