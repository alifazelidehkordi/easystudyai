---
name: medical-visuals
description: Find and review lecturer figures and supplementary anatomy, histology, physiology, pathology or imaging pictures in a no-API, source-anchored medical study workflow.
---

# Medical visuals — source first, reviewed, never invented

**Only add a visual when it makes the concept clearer.** Medical visuals are scientifically consequential: laterality, stain, labels, scale, diagnosis, licensing and patient privacy need care.

## Decision order

1. **The actual lecture.** Start with `python scripts/figures.py --query "topic"` and open the returned image or slide. Cite the original lecture and exact anchor. The tool indexes Markdown links, not meaning, and you must visually inspect.
2. **A true explanatory schematic.** For processes and causal flows, prefer a small Mermaid diagram, verified arrow-by-arrow. Label it *educational schematic*; never present synthetic radiology/microscopy/pathology as authentic.
3. **An external educational visual, only when needed.** First create a grounded need tied to the original lecturer page:

```sh
python scripts/visual_requests.py request \
  --source renal-pdf.md --anchor "Page 4" \
  --topic "normal renal corpuscle PAS histology" \
  --kind histology --reason "Need a comparison of glomerulus and surrounding tubules"
```

The request must cite an actual `course/processed/*.md` source and existing page/slide heading. `visual_requests.py search --query "..."` returns an ordinary browser URL to the Wikimedia Commons image-search page. **The script does not fetch results, call an image or AI API, or rank scientific credibility**.

If your harness supports normal browsing, follow the link and inspect the candidate file description, original metadata and license. If not, give the learner the link and explain that research and download are manual. Never hallucinate a picture filename or a source attribution.

## Attach, review, use

After obtaining the image with permission, record the original source page, actual creator and actual license:

```sh
python scripts/visual_requests.py attach REQUEST_ID \
  --file /path/to/downloaded.png \
  --title "Renal corpuscle, PAS stain" \
  --source-url "https://the-real-source-page" \
  --creator "Exact credited creator" --license "Exact published license"
```

This starts with status **attached / not approved**. Confirm orientation, image type, stain/scale/labels, educational relevance, identifiable-patient risk, license permissions and attribution conditions. **Only after real human review**, use:

```sh
python scripts/visual_requests.py approve REQUEST_ID --checked-medical --checked-rights
python scripts/visual_requests.py embed REQUEST_ID
```

The flags record human attestations and do not independently certify medical accuracy. The approved embed preserves creator/license/source and labels the image as **external supplementary**, not a slide from the professor. Images and request ledger are private via gitignore.

When unsure, give a **text explanation plus the unapproved candidate link** rather than embed a questionable image. Keep existing `scripts/add_image.py` for simple local cataloging outside the request workflow, but prefer `visual_requests.py` when teaching from a specific lecture.

## Special cautions
- Anatomy: check correct anatomical structures, labels, laterality and the view.
- Histology/pathology: check staining, disease vs normal distinction and magnification.
- Radiology: check imaging modality, orientation, phase and label accuracy.
- Do not use protected patient images or assume online availability means reuse rights.
- A missing figure is preferable to a wrong picture.
