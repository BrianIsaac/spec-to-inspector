# The evaluation protocol

Written on 11 October 2026, before the bench was run on the labelled set,
and not changed after. The bench records this file's SHA-256 in
`results/stage1/bench.json`, and its history in git shows when it was
written. If a later reader finds the protocol wanting, the remedy is a new
protocol and a new run, both dated, never an edit of this one.

## What is measured

Clause-citation accuracy: shown a flagged area of a board, does the judge
cite the clause of the specification that covers the defect there. It is
measured on the whole pipeline as it ships, from the specification's PDF to
the decision, with nothing chosen by hand in between.

## The labelled set

`eval/clause_labels.csv`: all 200 anomalous test images of VisA's pcb1 and
pcb4 (100 each; VisA's own one-class split, `split_csv/1cls.csv`). No image
is left out, for any reason.

The labels are not made by hand. Each row is a line of VisA's
`image_anno.csv`, which names the image's defect type or types, mapped to
the numbered heading of the specification that covers each type through
the written table of `eval/clause_mapping.md`. Twenty rows, chosen by a
fixed rule (`eval/spot-check-2026-10-11.md`), are checked against the image
by the operator; the figures do not wait for that check and do not change
with it, and its result is reported beside them.

- **Single-defect images, 135** (pcb1 91, pcb4 44): VisA names one defect
  type, so one heading is expected.
- **Multi-defect images, 65** (pcb1 9, pcb4 56): VisA names two or three
  types, so two or three headings are expected.

Two properties of the set, known before the run. No single-defect image
shows pcb4's `dirt`: it never occurs alone, so the headline figure never
exercises clause 5.1. And only 16 of the 135 single-defect images expect a
clause with a size limit (14 scratches on pcb1, 2 on pcb4).

The good boards of the same test split (pcb1 100, pcb4 101) are run too,
for the false alarms.

## The run

One command, `spec-to-inspector bench`, with its defaults, with the VLM
server up as `scripts/serve_vlm.sh start` starts it.

1. **The specification.** `specs/pcb-spec.pdf` is parsed as the `parse`
   verb parses it. The clause table that comes out must equal the tracked
   `specs/pcb-spec.clauses.json`, or the run stops; it is the table the
   judge is given.
2. **The anomaly model.** The trained PatchCore model of each part scores
   that part's whole test split, anomalous and good, into a run directory
   of the bench's own. Nothing is trained: the models are the ones the
   anomaly unit trained, and their thresholds are theirs.
3. **The judge.** Every image with a flagged area is judged as `inspect`
   judges it: up to three areas in rank order, most anomalous first,
   stopping at the first reject. Two switches are set, and both are part of
   this protocol:
   - **The corrections store is empty.** No correction is recalled into
     any prompt. The proof is on every decision: `corrected.in_prompt` is
     false and every region's `corrections` is empty. A run in which that
     fails for one decision is void.
   - **Every question is asked cold.** The server's prompt cache is off for
     each request (`cache_prompt` false), so an answer does not depend on
     what the server evaluated before. Asked with the cache on, the same
     image has been seen to change class between askings.

A run in which the server could not be reached for any area is void and
writes no figures.

## The citation

For an image, the citation is the **heading id** in the judge's validated
answer about **region 1**, the area with the highest anomaly score (for
example `5.6`). The heading is what the model chooses. The row of the
clause table that is then applied (`5.6.1`, `5.6.2` or `5.6.3`) is chosen
by code from the zone the area was measured in; it is a measurement's
outcome, it is reported beside the figures, and it is not what is scored.

An image has **no citation**, and counts as wrong wherever a citation is
scored, when the anomaly model flagged no area on it, when region 1 was not
put to the judge, when no valid answer came after one retry, or when the
judge answered that no clause applies.

The citation is scored whether or not region 1 lies on the labelled defect:
the model is asked about the area it is shown, and the figure is of the
pipeline, not of the judge alone. How often region 1 does lie on the defect
is reported beside the figure.

## The figures

Every proportion is given as a count, its N, and the 95% Wilson score
interval (z = 1.959964, no continuity correction):

    centre = (p + z^2 / 2n) / (1 + z^2 / n)
    half   = z * sqrt(p(1 - p)/n + z^2 / 4n^2) / (1 + z^2 / n)

1. **The headline: strict clause-citation accuracy, N = 135.** Over the
   single-defect images: the share whose citation is the expected heading.
   Given for both parts together and for each part (N = 91 and N = 44).
   Beside it, never in its place:
   - how many of the 135 the anomaly model flagged, and on how many region
     1 lies on the labelled defect: the ceiling the anomaly model sets;
   - the same accuracy over the flagged images only, and over the images
     whose region 1 lies on the labelled defect: the judge's own share,
     named as conditional;
   - for the correct citations, the row id code applied and the outcome of
     region 1 (reject, accept, or needs review with its cause).
2. **The lenient figure, N = 65.** Over the multi-defect images: the share
   whose citation is the heading of **any** of the image's defect types.
   It is called the lenient figure wherever it appears, and it is never
   pooled with the headline: no figure over all 200 images is given.
3. **The per-region figure.** VisA's masks number their defect types, so
   the types under region 1 are known. Over the images of the labelled set,
   single and multi, whose region 1 lies on exactly one defect type (the
   `region1` column of the labelled set says `one type`): the share whose
   citation is that type's heading. It is the only figure that scores a
   multi-defect image exactly, and the only one that exercises `dirt`.
4. **The confusion table**, per part, over the single-defect images: the
   expected defect type against the type of the heading cited, with columns
   for "no clause applies", "no valid answer", "not asked" and "not
   flagged". A second table does the same over the images of figure 3.
   How often the class the model named is not the class of the heading it
   cited is counted beside them.
5. **Needs review, by cause, at both levels.** Over the 200 anomalous
   images: the boards accepted, rejected and referred, the referred ones by
   `review_cause`; and over every area put to the judge on those boards,
   the same by the area's cause. An anomalous board that was not flagged is
   an accept the pipeline got wrong, and is counted as its own line.
6. **The false alarms on good boards**, beside the accuracy and never
   folded into it. Over the good test boards of each part: how many the
   anomaly model flagged, and what became of those: rejected (a false
   reject), referred for review, or accepted; and what the judge cited on
   them. The same needs-review breakdown as in 5 is given for them.
7. **Time per image, by stage**: parsing the specification (once per
   specification); the anomaly model, per image; measuring and drawing a
   flagged image's areas; the VLM's answers, per question and per flagged
   image; and the whole of a flagged image, end to end. Medians and 95th
   percentiles where there is a distribution.
8. **Minutes from specification to a working inspector**: the parse time
   measured in this run plus the fit time recorded when each part's model
   was trained. Training is not repeated here; the figure says so.
9. **Peak GPU memory by stage**, read from `nvidia-smi` for the process
   concerned: the bench's own process while the anomaly model scores, the
   VLM server's while it answers, and the card as a whole.

## What the figures are not

- **Not held out.** VisA's PCB test split is the only labelled data there
  is. The anomaly model's threshold was chosen by Anomalib on this same
  split, so which boards are flagged, and every false-alarm count, is tuned
  on the test images. The judge's prompt was written by the judge unit with
  sight of answers on some of these images. Nothing in the pipeline was
  changed after this protocol was written.
- **Not a figure for the corrections loop.** The store is empty throughout.
- **One specification, one model, one quantisation, one laptop.** The demo
  specification written for this entry; Qwen3-VL-8B-Instruct at Q4_K_M
  under llama.cpp on an RTX 5070 Ti laptop GPU.

## Reproducing

The command is run twice from the same state. Asked cold, the judge should
give the same answer to the same question; the second run records how many
of its answers on region 1 (class, heading, sentence) and how many board
outcomes differ from the first. The tracked file is the second run's. If
any figure of this protocol differs between the two runs, both values are
reported.

## One comparison, declared in advance

The server ships with `--image-min-tokens 1024`, llama.cpp's advice for
this model family. With the model's own minimum (`IMAGE_MIN_TOKENS=0`) an
answer comes about three times sooner. If time allows, the same command is
run once more against a server started that way, into files of its own,
and reported as a comparison. The headline is the shipped setting's
whichever of the two is higher.
