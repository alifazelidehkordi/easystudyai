---
name: review
description: Track medical-school learning after interactive quizzes; create professor-note-grounded review questions and revisit weak topics using local scripts/study.py.
---

# Review and retention

This skill adds persistent review to **Probe → Plan → Teach**. It works with both Codex CLI and Pi without any model API, scheduler service, or plugin.

1. **At the beginning of a review session** run `python scripts/study.py due`. If there are due cards, offer to review them before starting new concepts. Reveal answers only after the learner attempts a question.
2. **After teaching a substantive concept**, propose one short, specific active-recall question for the learner to retain. Do not make dozens of duplicates or reward irrelevant trivia.
3. Verify the full question and answer against the actual imported lecture Markdown and matching page/slide. Only then create it using `python scripts/study.py add --topic "..." --question "..." --answer "..." --source lecture-pdf.md --anchor "Page 3"`. If the relevant source/anchor is missing, explicitly do not store it as lecture-grounded. For external supplements, keep a separate note; do not mislabel them as professor content.
4. In a review round: display only the **question**, receive the learner's answer, then use `python scripts/study.py reveal CARD_ID` and explain it clearly. Ask the learner whether they want **again**, **hard**, **good** or **easy**, or propose a rating with their confirmation. Then run `python scripts/study.py grade CARD_ID --rating good` with their selected rating.
5. **Never** auto-grade unseen answers or assume the student understands because an explanation was presented. Correct but lucky guesses should generally remain harder review items.
6. When finishing, show `python scripts/study.py stats` and note the next review targets and any misunderstandings.

The simple review stages are intentionally transparent: again = due today, hard = no promotion / due tomorrow, good = next interval, easy = advance two intervals. Data is kept locally in gitignored `course/progress.json`; it is not synced across machines.

The importer is only a text extraction cache. If a question depends on a figure, confirm the visual with `python scripts/figures.py --query "..."`, view the original image and cite its page or slide. Do not assume extracting a file validates its medical content.
