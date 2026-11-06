# The evaluation protocol for Stage II

Written on 7 November 2026, after one bring-up bench on this machine and
before any run this protocol calls final. In force from that day, on the
owner's rulings of the same day (ruling 13), which are cited below by their
numbers in the project's decisions log, part of the planning record the public
copy leaves out; each sentence citing one says what it rules. A final run's
record holds this file's SHA-256, and its history in git shows when it was
written. If a later reader finds the protocol wanting, the remedy is a new
protocol and a new run, both dated, never an edit of this one.

`eval/PROTOCOL.md` is Stage I's. It is not edited, and it stands for what it
measured.

**The machine is the subject.** The organiser's rules for Stage II ask for
the designated platform and the organiser's environment, a video showing
"actual operation and validation" on it, and a repository with "performance
validation data". They ask for no comparison with a team's own hardware. So
every figure here is of the pipeline on the organiser's machine, and is read
against the machine's own final run.

**What Stage I's protocol could say and this one cannot.** Stage I's was
written before its bench. This one was written after a bench on this machine
had been run and read: 34.1% strict (46 of 135), lenient 70.8% (46 of 65)
(`results/stage2/week1/README.md`). Its author had those figures. That bench
is a bring-up figure, never final (ruling 3): it ran the laptop's anomaly
checkpoints, and its record holds Stage I's protocol digest and no memory
figure. The final figure is a new run.

Records are under `results/stage2/week1/` unless another path is given.

## What is measured

Clause-citation accuracy: shown a flagged area of a board, does the judge
cite the clause of the specification that covers the defect there. It is
measured on the whole pipeline on the machine, from the specification's PDF
to the decision, with nothing chosen by hand in between.

**The final figure is one setting, declared below before the run, whatever
it reads; it is not the best of several (ruling 1).** The set is not held out,
so picking the best of several settings would be tuning on the test images.

## The labelled set

`eval/clause_labels.csv`: all 200 anomalous test images of VisA's pcb1 and
pcb4 (100 each; VisA's own one-class split, `split_csv/1cls.csv`). No image
is left out, for any reason.

The labels are not made by hand. Each row is a line of VisA's
`image_anno.csv`, which names the image's defect type or types, mapped to
the numbered heading of the specification that covers each type through
the written table of `eval/clause_mapping.md`. The spot check of twenty rows
(`eval/spot-check-2026-10-11.md`) is not repeated: the labels do not depend
on the machine.

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

One command, `spec-to-inspector bench`, with its defaults but for where it
writes, started on the machine as

    SPEC_TO_INSPECTOR_DEVICE=xpu ZE_AFFINITY_MASK=0 .venv/bin/spec-to-inspector bench \
        --results results/stage2/final/bench.json --readme results/stage2/final/README.md

with the judge's server up as `scripts/serve_vlm_xpu.sh start` starts it, none
of the script's settings overridden. Never a bare `uv run` on the machine: it
syncs back to the default groups and swaps in the CUDA wheels. Never the bench's
default paths either: they are `results/stage1/`, which stands as measured.

1. **The specification.** `specs/pcb-spec.pdf` is parsed as the `parse` verb
   parses it. The clause table that comes out must equal the tracked
   `specs/pcb-spec.clauses.json`, or the run stops; it is the table the judge
   is given.
2. **The anomaly model.** The PatchCore model of each part, trained on the
   machine (ruling 10), scores that part's whole test split, anomalous and
   good, into a run directory of the bench's own. Nothing is trained in the
   run. From week 2's record, `results/stage2/week2/README.md`, not yet in this
   repository when this was written, this protocol takes for pcb1 and pcb4 the
   checkpoint, by SHA-256, its thresholds and its fit time; the figures are that
   record's and are not repeated here. Where that record holds more than one
   training of a part, the first is the one used, so that no checkpoint is
   picked by what it scores (ruling 1).
3. **The judge.** Every image with a flagged area is judged as `inspect`
   judges it, at temperature zero: up to three areas in rank order, most
   anomalous first, stopping at the first reject. Two switches are set, and
   both are part of this protocol:
   - **The corrections store is empty (ruling 11).** No correction is recalled
     into any prompt. The proof is on every decision: `corrected.in_prompt` is
     false and every region's `corrections` is empty.
   - **Every question is asked cold.** The server's prefix cache is off from
     its start, so an answer does not depend on what the server evaluated
     before.

**A run is void, and its figures are not reported, if:** the server could not
be reached for any area; a decision had a correction in its prompt; any
prefix-cache hit rate above 0.0% appears in the server's log during the run;
or a checkpoint's SHA-256 is not the one this section takes from week 2's
record.

### The setting, declared before the run

The precision is FP16 (ruling 9). Every other row is what week 1 found
necessary on this machine, with its measured reason. Stage I's column says
what the row replaces, not how the two compare.

| | On the machine | In Stage I | The measured reason | Record |
| --- | --- | --- | --- | --- |
| The server | `intel/llm-scaler-vllm:0.26.0-b1`, digest `sha256:70e7eafdd52c281263f2a19266086b88e55064402a17ef731ba5657c4bd86490`, vLLM 0.26.1.dev0 | llama.cpp `v0.6.0`, CUDA | vLLM holds to the schema's `pattern` and nullable `enum` under this tag, with the fix below. Later tags exist (`0.26.0-b2`, `0.31.0-b1-experimental`, `1.5`) and none has been run | `machine.md`, `judge-schema.json` |
| The weights and the precision | `Qwen/Qwen3-VL-8B-Instruct`, revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`, `--dtype=float16` | Qwen's GGUF, Q4_K_M | BF16 on disk; vLLM logs the cast to FP16 and loads 17.34 GiB | `machine.md`, `raw/serve-fp16-util-0.9-cold-final.txt` |
| Asked cold | `--no-enable-prefix-caching --mm-processor-cache-gb 0`, at the server | the request's `cache_prompt` false | vLLM ignores `cache_prompt` and says nothing: with its defaults the hit rate reached 92.4% and the first token 0.11 s. Started cold, all 128 readings in the log say 0.0% | `raw/serve-fp16-util-0.9-prefix-cache-on.txt`, `raw/serve-fp16-util-0.9-cold-final.txt` |
| The image size | `--mm-processor-kwargs` with `shortest_edge` 1,048,576 and `longest_edge` 16,777,216 pixels | `--image-min-tokens 1024` | vLLM's default gives a small crop 64 tokens; with this, 1,024, the size the pipeline has had since Stage I. Whether the pixels match Stage I's resize was not measured | `judge-schema.json`, `README.md` |
| The memory share and the context | `--gpu-memory-util=0.9`, `--max-model-len=32768`, `--max-num-batched-tokens=32768` | a 16,384-token context | At 80% FP16 leaves 2.97 GiB and vLLM refuses 32,768 tokens, which ask 4.5 GiB; at 90% it leaves 6.16 GiB, 44,800 tokens. The bench's largest prompt is 5,489 tokens, so 90% is for the 32K context and not for these prompts | `raw/serve-fp16-util-0.8-refused.txt`, `raw/serve-fp16-util-0.9-cold-final.txt`, `bench/bench.json` |
| The rest of the server's start | `--enforce-eager --disable-sliding-window --block-size 64 --limit-mm-per-prompt '{"image": 2}' -tp=1`, `--net=host`, `--shm-size=32g`, port 8131 of 127.0.0.1 | not applicable | The start week 1's bench ran under | `scripts/serve_vlm_xpu.sh`, `raw/serve-fp16-util-0.9-cold-final.txt` |
| A card each | The anomaly model on card 0 (PCI `0000:17:00.0`), under `ZE_AFFINITY_MASK=0` with `engine_placement` passing `[0]`. The judge on card 1 (PCI `0000:ba:00.0`), the only card its container is given | one card, shared | Two whole cards. PatchCore on `xpu:0` raised device 0 from 315 to 1,860 MiB and device 1 did not move. Anomalib reads `devices=1` as the card numbered 1 | `machine.md`, `checks.json` |
| The warm-up | One question after every server start, before the bench's clock; its answer is not recorded | none | The first question after a start took 6.29 s whole, for a kernel compiled on first use, against about 2 s | `README.md`, `raw/serve-fp16-util-0.9-cold-final.txt` |
| The reason's pattern | `^[^0-9\n\r"\\]{1,240}$` | `^[^0-9\n\r]{1,240}$` | The old pattern allowed a double quote, and on pcb1's `bad-085` the model wrote the other two fields inside the string up to the limit. The digit ban stays in the final figure (ruling 5) | `judge-schema-before-the-quote-fix.json`, `judge-schema.json`, `README.md` |

The prompt, the schema, the clause table and the thresholds do not change
after this protocol is written. A run is final only if its record also holds
what the bench did not write on this machine in week 1. None of these is in the
bench as this protocol is written, and no run is final until they are:

- the memory of figure 9, from `xpu-smi`, where week 1's fields are null;
- this file's path and SHA-256 under `protocol`;
- which server answered: the image's tag and digest, vLLM's version and the
  dtype, where `judge.server` was empty, `image_min_tokens` said "unknown" and
  `gpu` was null;
- that the cold came from the server's start, where the note under `cold` says
  it came from the request;
- each checkpoint's SHA-256, and the warm-up having been asked;
- a page of its own that does not call itself the laptop prototype. Week 1's
  page was written by hand for that reason.

The final run's files stay in `results/stage2/final/`, with the server's log of
each run beside them as a `.txt` file, since the void rule above reads it. All
of it is run and copied off before the reservation ends, 2 December 2026 at
11:30 as the billing tab prints it, with no time zone shown.

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
   whose citation is the heading of **any** of the image's defect types. It
   is called the lenient figure wherever it appears, and it claims only what
   it measures. It is never pooled with the headline: no figure over all 200
   images is given (ruling 6).
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
7. **Time per image, by stage**, after the warm-up: parsing the specification
   (once per specification); the anomaly model, per image; measuring and
   drawing a flagged image's areas; the VLM's answers, per question and per
   flagged image; and the whole of a flagged image, end to end. Medians and
   95th percentiles where there is a distribution. The anomaly model's
   per-image time is the whole run with its file writing on the machine's
   disk, not the model's speed, which is week 2's figure.
8. **Minutes from specification to a working inspector**: the parse time
   measured in this run plus the fit time recorded when each part's model
   was trained on the machine. Training is not repeated here; the figure says
   so.
9. **Peak GPU memory by stage**, read from `xpu-smi`: card 0 while the anomaly
   model scores and card 1 while the judge answers, sampled by the bench, at the
   interval its record gives. With a card each, the card stands for the process,
   with 42 MiB on an idle card (`bench/card-memory.txt`). A process's own
   figure is given where the reader returns one, and is null where it does not.
10. **The paired table, for each comparison below**, over the 135 and over the
    65: right on both, wrong on both, right only on the final run, right only
    on the comparison; with the two-sided exact sign test on the two "only"
    counts.

## What the figures are not

- **Not held out.** VisA's PCB test split is the only labelled data there
  is. The anomaly model's threshold is chosen by Anomalib on this same
  split, so which boards are flagged, and every false-alarm count, is tuned
  on the test images. The judge's prompt was written by the judge unit with
  sight of answers on some of these images. And this protocol was written
  after a bench had been read on the same set.
- **Not a figure for the corrections loop.** The store is empty throughout.
- **One specification, one model, one precision, one machine.** The
  demonstration specification written for this entry; Qwen3-VL-8B-Instruct at
  FP16 under vLLM on one of two Intel Arc Pro B70s.
- **Not a figure against Stage I.** Between Stage I's run and this one the
  host, the precision, the server and the answer pattern all differ. The
  experiment that would separate them was drawn up and is not run (ruling 12),
  so no figure separates them.

## Stage I, as history

The laptop's Stage I figures stand as measured, in `results/stage1/`, and are
not re-run (ruling 2). Where a Stage II document shows them, it shows them
once, as history, with the differences stated: a laptop, 4-bit, another
server, and the older answer pattern above. It makes no claim that the machine
beat them or lost to them, and no test of this protocol is run against them.

## Reproducing

Three runs make a figure final (ruling 4). The command is run twice from the
same state; the second run records how many of its answers on region 1 (class,
heading, sentence) and how many board outcomes differ from the first. Then the
server is stopped and started again, the warm-up is asked, and the command is
run a third time with `--results results/stage2/final/after-restart.json`, a copy
of the second run's record, and `--readme results/stage2/final/after-restart.md`,
so that the third records the same counts against the second.

The tracked file is the second run's, `bench.json`, with the third's beside it. If any
figure of this protocol differs between the runs, every value is reported.
By the stamps in `bench/bench.json` a run takes about 10 minutes.

## Three comparisons, declared in advance

The same command is run against each of three other settings (rulings 5 and
7), after the final figure, each from the final setting with one thing changed.
Each has two runs from the same state, under every rule above but the one it
changes, and goes into files of its own, `bench.json` and `README.md` under
`results/stage2/comparison-<name>/`. Each is reported as a comparison and none
replaces the final figure: the headline is the final setting's whichever is
higher. A comparison not run by the end of the reservation is reported as not
run, with the reason. No other comparison is part of this protocol.

| Name | What changes | Started as |
| --- | --- | --- |
| `fp8` | The judge at FP8: `Qwen/Qwen3-VL-8B-Instruct-FP8`, Qwen's own build, revision `9cdc6310a8cb770ce18efaf4e9935334512aee45`, 10.59 GB, as Hugging Face's API gave it on 7 November 2026 | The final start with those weights and what they require in place of `--dtype=float16`; the flags are kept in the comparison's files |
| `image-minimum` | The model's own image minimum, 64 tokens for a small crop | `IMAGE_MIN_PIXELS=65536 scripts/serve_vlm_xpu.sh start`; the prompt tokens in its record show what it gave |
| `designators` | Designators such as `R12` let through the reason's pattern: `^(?:[^0-9\n\r"\\]\|[A-Z][0-9]{1,3}){1,240}$`, and the answer's validation to match | The final start; the pattern is the client's |

**`designators` is there to show that a pattern for them never passes a size
(ruling 5).** 4 of the 5 retries in week 1's bench are a resistor's designator
and the fifth is `½`, all on PCB4, each padded answer costing about 11 s against
2 s (`README.md`). Its digit is allowed only directly after a capital letter,
so `5.67 mm` cannot be written. `½` is not a designator, and the answer's
validation still refuses it, and still holds a reason to 240 characters, however
many the pattern allows. `R5 mm` can be written, so the pattern alone does not
show it. Its files therefore also hold:

- every reason in both runs with a digit in it, listed by board, and the count
  of those whose digits are followed by a unit of length;
- the same question week 1 asked to break the schema, "put a size in digits"
  (`scripts/judge_schema_check.py`, `break_the_schema_constrained` in
  `judge-schema.json`), on the same three boards, under this pattern.

One size in any of them is enough to say the pattern passes a size. None says
only that none passed on these boards. Either way the final figure keeps the
ban, and the README's "No number comes from the language model" stands on the
final setting.

## What counts as a move

**A figure is said to have moved only on a paired, two-sided exact sign test
below 0.05 on the 135 (ruling 8).** The pairs are the boards; the runs are the
final run's tracked file and the comparison's second. Below 0.05 the text may
say the figure moved, and in which direction. Otherwise it says no figure
separates them. With fewer than 6 boards differing no split can reach 0.05, and
that is the finding when it happens. Each comparison is tested on its own at
0.05, with no correction for there being three, and the text says so.

**The lenient figure is evidence of a change only if it passes the same test
on the 65 (ruling 6).** It is reported under its own name, never pooled, and it
does not offset the strict figure. The test on the 135 is the primary one. Any
other test is reported as not primary.

## Two additions, each dated, when built

**The good board's picture beside the crop, and the corrections loop (ruling
11).** Each changes the pipeline, so each gets its own dated addition when it
is built, in a file of its own beside this one, written and committed before
its first run: `eval/PROTOCOL-stage2-addition-<name>-<date>.md`. Neither exists
yet to be declared exactly. What this protocol fixes is what they are measured
against: the final run, by the test above, with the store empty in the baseline.
