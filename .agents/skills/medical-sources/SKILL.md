---
name: medical-sources
description: Trace medical claims to actual professor pages and check lecture import quality before teaching; external context requires explicit provenance.
---

# Medical-source discipline

1. Read `course/COURSE.md`. Before using an imported lecture, run `python scripts/audit_lecture.py course/processed/LECTURE.md`. It checks missing figures and text-layer gaps, not medical validity. Scanned pages, abbreviated text and complex charts require opening the original page/slide; never silently treat an incomplete text import as the whole lecture.
2. Locate relevant passages with `python scripts/search_notes.py "key terms"`, then read the full sections and, where needed, corresponding PDF/PowerPoint/Word originals.
3. Cite course statements as `(LectureName.pdf, p. 4)`, `(LectureName.pptx, slide 7)`, or `(Handout.docx, paragraph 12)`. Only use anchors actually present; DOCX extractor paragraph numbers are not printed pages. Never invent references.
4. Record provenance of each nontrivial claim:
   - **COURSE NOTE**: lecturer-provided material and exact location. Sets learning/exam scope, not necessarily medical correctness.
   - **EXTERNAL VERIFIED**: inspected textbook/guideline/paper, with title, date/edition and URL when available.
   - **TEACHING EXAMPLE**: simplified schematic, explanatory analogy or hypothetical clinical vignette.
5. If the course conflicts with current evidence, show the versions side-by-side and cite the difference. For fast-changing clinical guidelines, check date/jurisdiction or state verification is unavailable.
6. Images discovered outside the lecture are **external supplemental sources**, not lecture originals. Follow `medical-visuals` review and attribution workflow.
7. Do not use model memory as proof or invent exact page numbers, journal studies, contraindications or numeric ranges.
8. Do not upload identifiable patient data. Respect third-party rights, and keep lecture content out of public GitHub commits.
