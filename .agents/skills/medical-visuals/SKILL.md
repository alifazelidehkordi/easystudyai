---
name: medical-visuals
description: Incorporate source-attributed, medically checked anatomical/histological/physiological visuals and simple explanatory diagrams when they improve learning.
---

# Medical visuals

Choose images for genuine learning needs: spatial anatomy, microscopic patterns, disease morphology, imaging orientation, dynamic processes, clinical decision trees.

1. **First** reuse figures already in the professor's lecture, keeping their page/slide reference. If source extraction omitted a figure, review/render the original page.
2. **Next** consider original schematic Mermaid diagrams for processes or causal mechanisms; label these "schematic", not as clinical photographs. Diagram edges, legends, laterality and scales require checking.
3. **Then**, if permitted, use the harness's normal browser/research abilities to locate external images from reputable sources such as Wikimedia Commons (license-specific), institutional teaching sites or open-access atlases. Never assume a web image is reusable.
4. Add an already downloaded file with `python scripts/add_image.py --file /path/to/image.png --title "..." --source-url "https://..." --creator "..." --license "..." `. This local tool is offline; the student/assistant must confirm both source/terms and medical accuracy before use.
5. Store images under `course/visuals/`; provide Markdown image reference, caption, external link and creator/license. Image files must not be copied into public commits automatically.
6. Do **not** generate a fake X-ray, histology slide, CT, pathology photograph, or anatomical atlas labeled as authentic. If uncertain about stain, view, magnification, structure or rights, omit rather than mislabel.

Source credibility, citation and accuracy are more important than quantity of visuals.
