# indrajala-datasets-perseus-parallel

Greek-English parallel texts, aligned by citation, for training translation models (roadmap step
15 of [`indrajala-ml`](https://github.com/davidbarkhuizen/indrajala-ml): cross-attention and an
encoder-decoder model). Two corpora:

- **The histories:** Herodotus, Thucydides, Pausanias (Books 1-5), Xenophon's *Anabasis*,
  *Hellenica* and *Cyropaedia*, and Diogenes Laertius, section by section (book.chapter.section).
  14,602 pairs, 4.75M Greek and 5.76M English characters.
- **The New Testament:** all 27 books, Westcott and Hort's Greek with the World English Bible,
  verse by verse (chapter.verse). 7,908 pairs, 0.83M Greek and 0.92M English characters.

This repo holds *reproducible cleaned pairs*: the sources are the Perseus Digital Library's TEI
texts, pinned to one commit of
[PerseusDL/canonical-greekLit](https://github.com/PerseusDL/canonical-greekLit) with each file's
checksum (`sources.json`), and `clean.py` rebuilds every file in `data/` and `report.md` from them
byte for byte (`python3 clean.py --check`).

## contents

```
clean.py                               - fetches the pinned sources, verifies, aligns, cleans, splits, reports
sources.json                           - the source files at the pinned commit, with their SHA-256
report.md                              - the alignment report (written by clean.py)
metadata.json                          - repo-level metadata (provenance, commit, file list)
LICENSE-TEXT.md                        - the texts' licence (CC BY-SA 4.0) and the copyright check per volume
data/
  histories.jsonl                      - 14,602 pairs
  histories.jsonl.metadata.json        - checksum, counts by work and split, vocabularies
  new-testament.jsonl                  - 7,908 pairs
  new-testament.jsonl.metadata.json
```

Each line of a `.jsonl` file is one pair, in text order:

```json
{"work": "herodotus", "ref": "1.1.0", "split": "train", "grc": "Ἡροδότου Ἁλικαρνησσέος ἱστορίης ἀπόδεξις ἥδε, ...", "eng": "This is the display of the inquiry of Herodotus of Halicarnassus, ..."}
```

`ref` is the Perseus citation; a pair joined from two units (below) spans both, as `3.16-17`.

## quick start

```python
import json

pairs = [json.loads(line) for line in open("data/histories.jsonl", encoding="utf-8")]
train = [(p["grc"], p["eng"]) for p in pairs if p["split"] == "train"]
```

## the translations

| work | Greek | English |
| --- | --- | --- |
| Herodotus, *Histories* | Godley (Loeb, 1920-25) | A. D. Godley (Loeb, 1920-25), modernised by Perseus |
| Thucydides, *History of the Peloponnesian War* | H. Stuart Jones (Oxford; Perseus's source the printing of 1910 and the revised printing of 1942) | Richard Crawley (1874; Perseus's source Dent's edition of 1914) |
| Pausanias, *Description of Greece*, Books 1-5 | F. Spiro (Teubner, 1903) | W. H. S. Jones (Loeb, 1918) and H. A. Ormerod (Loeb, 1926) |
| Xenophon, *Anabasis* | E. C. Marchant (Oxford, 1904; reprinted 1961) | C. L. Brownson (Loeb, 1921-22) |
| Xenophon, *Hellenica* | E. C. Marchant (Oxford, 1900; reprinted 1968) | C. L. Brownson (Loeb, 1918-21) |
| Xenophon, *Cyropaedia* | E. C. Marchant (Oxford, 1910; reprinted 1970) | Walter Miller (Loeb, 1914) |
| Diogenes Laertius, *Lives of Eminent Philosophers* | R. D. Hicks (Loeb, 1925) | R. D. Hicks (Loeb, 1925) |
| The New Testament | B. F. Westcott and F. J. A. Hort (1881; Perseus's source Harper's printing, 1882-92) | the World English Bible (Rainbow Missions, 2000-24) |

Thucydides has three candidate English translations at the pinned commit: Crawley, C. F. Smith
(Loeb) and Henry Dale. `clean.py` measures each one's alignment with the Greek and keeps the best,
Crawley (3,585 of 3,587 pairs in ratio, none unmatched; `report.md`). Hobbes's
seventeenth-century English was not a candidate.

Pausanias stops at Book 5: Books 6-10 are from Jones's volumes of 1933 and 1935, whose copyright
is unchecked. Books 1-5 are in the public domain in the United States but not yet in countries
with terms of life plus 70 years, until the end of 2033 and 2034 (`LICENSE-TEXT.md`): outside the
United States, check before using the Pausanias pairs, or leave them out.

## the alignment

A pair is the text of one citation unit on both sides, at the deepest level both files number:
sections in the histories, verses in the New Testament. Every unit of the works here aligns except
those `report.md` lists:

- **Renumbered** where the two files number a unit differently (`clean.py`'s renames): Godley's
  preface and eight Herodotus sections numbered past the Greek's; the doxology of Romans (Westcott
  and Hort's 16.25-27, the WEB's 14.24-26); and three places in the New Testament where one side
  joins verses the other splits.
- **Joined** where the two sides end a unit at different points, so neighbours trade text: a pair
  whose English is under 0.5 or over 2.5 times the Greek's length is joined with its neighbour in
  the chapter when the join is in ratio (46 joins, 14 of them in the histories). No pair is
  out of ratio after the joins.
- **Dropped:** units on one side only (Mark's shorter ending in Westcott and Hort, 16.20a; Mark
  15.28 in the WEB), units empty on a side (verses Westcott and Hort omit, such as Matthew 17.21),
  and 24 sections of Diogenes Laertius whose English quotes the Greek it translates (Hicks's puns
  and etymologies).

**The New Testament's two texts differ.** The WEB translates the Majority Text, not Westcott and
Hort's: besides the verses Westcott and Hort omit, some verses carry clauses the Greek here lacks
(Romans 8.1's "who don't walk according to the flesh, but according to the Spirit"). Only the
largest differences show as length outliers, so a model trained on this corpus sees some English
with no Greek behind it.

## the cleaning

Both sides:
- **Dropped with their text:** notes, headings, bibliographic references, figures, the reading an
  editor rejects in a choice, and the place-name glosses Perseus added to Godley's English
  ("Egypt [30,27] (nation)").
- **Kept:** the editors' additions and corrections, the passages they judge interpolated (the
  translators translate them), speakers' labels, quotations and verse.
- **Removed:** page, line and milestone breaks, and the editors' cruxes (the dagger).
- **Errata:** 14 typos and stray marks, each an exact replacement in one pair (`clean.py`'s
  `ERRATA`).
- **Layout:** a pair is one line of each language, whitespace collapsed.

English: ASCII, as `indrajala-ml`'s other corpora are (accents stripped, dashes as `-` and `--`,
quotes straight); Hicks's lacuna marks (`*`) removed; the translators' brackets kept.

Greek: Unicode NFC, accents and breathings kept; the elision marks unified as U+2019; the
editions' sigla removed with their content kept (brackets for doubtful, supplied or deleted words,
Westcott and Hort's double brackets, the marks of lacunae); 16 combining marks the sources attach
to no letter dropped.

## the splits

A whole book of each work is held out, a different book in each: Herodotus 5, Thucydides 6,
Pausanias 2, *Anabasis* 3, *Hellenica* 4, *Cyropaedia* 7, Diogenes Laertius 8; in the New
Testament, John and Romans. The synoptic gospels (Matthew, Mark and Luke) share passages, so all
three are in train. Each held-out book's chapters, in order, are cut in two at its middle pair:
the first part is validation, the rest test.

| corpus | train | validation | test |
| --- | ---: | ---: | ---: |
| histories | 12,922 | 899 | 781 |
| new-testament | 6,606 | 699 | 603 |

`report.md` lists the held-out pairs whose Greek shares at least half its 8-letter shingles with a
train pair's: none in the histories, 11 in the New Testament (John's parallels with the synoptics,
and Romans's quotations shared with other letters, such as Genesis 15.6 in Romans 4.3 and James
2.23).

## windows

Pairs vary in length: the histories' median is about 250-575 Greek characters by work, the New
Testament's about 100. 68 history pairs have a side longer than 1,024 characters, and no New
Testament pair is longer than 512 (`report.md` lists each). The pairs are window-agnostic: a
consumer packing them into windows drops the ones that don't fit.

## reproducing

```
python3 clean.py --check            # fetch, verify, rebuild, compare with the committed files
python3 clean.py --cache .cache     # rebuild, keeping the fetched sources in .cache (verified on every read)
```

Python 3.10+, standard library only; about 50 seconds and under 1 GB.

## provenance

The TEI texts are the Perseus Digital Library's (Tufts University, Gregory Crane, editor in
chief), at commit `70427323b61267cdcd0256b9b02009c23392de07` of PerseusDL/canonical-greekLit, the
commit `indrajala-datasets-euclid-heath` pins. `sources.json` gives each file's path and checksum,
and `clean.py` verifies them.

## versioning

Consumers should pin to a specific tag or commit, not `main`; `metadata.json`'s `version` field is
this repo's own packaging version.

## license

- **The texts** (`data/*.jsonl`) are adapted from Perseus's and released, as Perseus's are, under
  **CC BY-SA 4.0**: attribution, and adaptations under the same licence. See `LICENSE-TEXT.md`,
  which also records the copyright check of each translation and edition.
- **This repo's packaging** (this README, `clean.py`, `sources.json`, `metadata.json`, the layout)
  is MIT-licensed; see `LICENSE`.
