"""
Rebuilds this repository's Greek-English parallel corpora from the Perseus Digital Library's TEI
texts, fetched at a pinned commit of PerseusDL/canonical-greekLit and checksum-verified
(sources.json), aligned by citation, cleaned, split and reported:

- data/histories.jsonl: Herodotus (Godley), Thucydides (the translation that aligns best of the
  candidates, measured here), Xenophon's Anabasis and Hellenica (Brownson) and Cyropaedia (Miller),
  Diogenes Laertius (Hicks); aligned section by section (book.chapter.section).
- data/lives.jsonl: Plutarch's Parallel Lives with their comparisons, Perrin's Greek and English
  (Loeb, 1914-26), 66 works; aligned section by section (chapter.section; book.chapter.section in
  Agis and Cleomenes and the Gracchi).
- data/*.jsonl.metadata.json: each file's checksum, counts and vocabularies;
- report.md: the alignment report (pairs, lengths, what didn't align, the pairs too long for a
  window, length-ratio outliers, near-duplicates across the split, the vocabularies).

A pair is the text of one citation unit on both sides, the deepest units both files number, matched
by ref after the renames (Work.greek_renames, english_renames: where the files number a unit
differently, or one joins units the other splits). A unit on one side only is dropped (the report
lists each); a unit one file divides and the other doesn't is an error. A pair out of length ratio
is joined with a neighbour in its chapter where the two sides end a unit at different points
(merge_drift); errata (ERRATA) are fixed in the cleaned pairs.

Cleaning, both sides:
- dropped with their text: notes, headings, bibliographic references (bibl), figures, the
  reading an editor rejects in a choice (sic, orig), and Godley's place-name glosses (reg outside a
  choice, which Perseus added: "Egypt [30,27] (nation)");
- kept: the editors' additions (add) and corrections (corr), and the passages they judge
  interpolated (del: the translators translate them, often in brackets, so a pair without them
  would hold English with no Greek behind it), speakers' labels, quotations, verse;
- markup only: page, line and milestone breaks; the editors' cruxes (the dagger) removed;
- a pair is one line, whitespace collapsed.
English: normalized to ASCII (accents stripped, dashes as - and --, quotes straight); a character
NFKD can't reduce, other than those spelled out (SPELLED), is an error, not a silent change.
Greek: Unicode NFC, accents and breathings kept; the elision marks unified as U+2019.

Splits hold out a whole book of each history, a different book in each (Work.held_out), and whole
Lives in Plutarch, each with its pair and their comparison (LIVES_HELD_OUT); a held-out book's or
Life's chapters, in order, are split in two at the middle pair: the first part validation, the rest
test. Everything else is train.

    python3 clean.py                  # fetch, verify, align, clean, write data/ and report.md
    python3 clean.py --check          # the same, then compare with the committed files, byte for byte
    python3 clean.py --cache DIR      # keep the fetched sources in DIR (verified on every read)

Python 3.10+, standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field

COMMIT = "70427323b61267cdcd0256b9b02009c23392de07"
BASE_URL = f"https://raw.githubusercontent.com/PerseusDL/canonical-greekLit/{COMMIT}/"
HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.path.join(HERE, "sources.json")
OUT = {"histories": "data/histories.jsonl", "lives": "data/lives.jsonl"}
REPORT = "report.md"

TEI = "{http://www.tei-c.org/ns/1.0}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

# dropped with their text
DROPPED = {f"{TEI}{tag}" for tag in ("note", "head", "bibl", "figure", "gap")}
# in a choice, the reading kept and the reading dropped
CHOICE_KEPT = {f"{TEI}corr", f"{TEI}reg", f"{TEI}expan"}
# markup only: a space
BREAKS = {f"{TEI}{tag}" for tag in ("lb", "pb", "milestone", "cb")}
# blocks: a space after each, so their words don't run together
BLOCKS = {f"{TEI}{tag}" for tag in ("p", "l", "lg", "item", "sp", "speaker", "label", "quote", "q", "cit", "list")}

# English characters NFKD doesn't reduce to ASCII
SPELLED = {
    "—": "--",
    "–": "-",
    "‒": "-",
    "‐": "-",
    "‑": "-",
    "―": "--",
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "«": '"',
    "»": '"',
    "æ": "ae",
    "Æ": "Ae",
    "œ": "oe",
    "Œ": "Oe",
    " ": " ",
    "…": "...",
    "·": ".",
    "′": "'",
    "″": '"',
}
# the elision marks Perseus's Greek texts use, unified
ELISION = {"ʼ": "’", "᾽": "’", "᾿": "’", "'": "’", "‘": "’"}
CRUX = "†"

WINDOWS = (256, 512, 1024)


@dataclass(frozen=True)
class Work:
    corpus: str
    name: str
    title: str
    greek: str
    english: tuple[str, ...]  # one translation, or the candidates the cleaner chooses among
    books: tuple[str, ...] | None = None  # the top-level units included (None: all)
    held_out: str | None = None  # the top-level unit held out; "*": the whole work
    # a citation unit renumbered (old ref -> new ref) where the two files number it differently;
    # units renumbered to one ref are joined, in order
    greek_renames: dict[str, str] = field(default_factory=dict, hash=False, compare=False)
    english_renames: dict[str, str] = field(default_factory=dict, hash=False, compare=False)


def perseus(work: str, version: str) -> str:
    group, text = work.split(".")
    return f"data/{group}/{text}/{group}.{text}.{version}.xml"


HISTORIES = [
    Work(
        "histories",
        "herodotus",
        "Herodotus, Histories",
        perseus("tlg0016.tlg001", "perseus-grc2"),
        (perseus("tlg0016.tlg001", "perseus-eng2"),),
        held_out="5",
        # Godley's English: the preface numbered pr, and eight sections numbered one or more past the
        # Greek's (the chapter's sections 1, 2, 4 for the Greek's 1, 2, 3)
        english_renames={
            "1.1.pr": "1.1.0",
            "6.11.4": "6.11.3",
            "6.49.3": "6.49.2",
            "6.58.6": "6.58.3",
            "7.19.3": "7.19.2",
            "7.37.4": "7.37.3",
            "7.41.3": "7.41.2",
            "7.67.3": "7.67.2",
            "7.83.3": "7.83.2",
        },
    ),
    Work(
        "histories",
        "thucydides",
        "Thucydides, History of the Peloponnesian War",
        perseus("tlg0003.tlg001", "perseus-grc2"),
        (
            perseus("tlg0003.tlg001", "perseus-eng6"),
            perseus("tlg0003.tlg001", "1st1K-eng1"),
            perseus("tlg0003.tlg001", "1st1K-eng2"),
        ),
        held_out="6",
    ),
    Work(
        "histories",
        "anabasis",
        "Xenophon, Anabasis",
        perseus("tlg0032.tlg006", "perseus-grc2"),
        (perseus("tlg0032.tlg006", "perseus-eng2"),),
        held_out="3",
    ),
    Work(
        "histories",
        "hellenica",
        "Xenophon, Hellenica",
        perseus("tlg0032.tlg001", "perseus-grc2"),
        (perseus("tlg0032.tlg001", "perseus-eng2"),),
        held_out="4",
    ),
    Work(
        "histories",
        "cyropaedia",
        "Xenophon, Cyropaedia",
        perseus("tlg0032.tlg007", "perseus-grc2"),
        (perseus("tlg0032.tlg007", "perseus-eng2"),),
        held_out="7",
    ),
    Work(
        "histories",
        "diogenes",
        "Diogenes Laertius, Lives of Eminent Philosophers",
        perseus("tlg0004.tlg001", "perseus-grc2"),
        (perseus("tlg0004.tlg001", "perseus-eng2"),),
        held_out="8",
    ),
]

# Plutarch's Lives in Perrin's Loeb (both texts his): (work number, name, title); the files are
# perseus-grc2 and perseus-eng2 but where VERSIONS says otherwise
LIVES_TABLE = [
    (1, "theseus", "Theseus"),
    (2, "romulus", "Romulus"),
    (3, "theseus-romulus", "Comparison of Theseus and Romulus"),
    (4, "lycurgus", "Lycurgus"),
    (5, "numa", "Numa"),
    (6, "lycurgus-numa", "Comparison of Lycurgus and Numa"),
    (7, "solon", "Solon"),
    (8, "publicola", "Publicola"),
    (9, "solon-publicola", "Comparison of Solon and Publicola"),
    (10, "themistocles", "Themistocles"),
    (11, "camillus", "Camillus"),
    (12, "pericles", "Pericles"),
    (13, "fabius", "Fabius Maximus"),
    (14, "pericles-fabius", "Comparison of Pericles and Fabius Maximus"),
    (15, "alcibiades", "Alcibiades"),
    (16, "coriolanus", "Coriolanus"),
    (17, "alcibiades-coriolanus", "Comparison of Alcibiades and Coriolanus"),
    (18, "timoleon", "Timoleon"),
    (19, "aemilius", "Aemilius Paulus"),
    (20, "timoleon-aemilius", "Comparison of Timoleon and Aemilius Paulus"),
    (21, "pelopidas", "Pelopidas"),
    (22, "marcellus", "Marcellus"),
    (23, "pelopidas-marcellus", "Comparison of Pelopidas and Marcellus"),
    (24, "aristides", "Aristides"),
    (25, "cato-major", "Marcus Cato"),
    (26, "aristides-cato", "Comparison of Aristides and Cato"),
    (27, "philopoemen", "Philopoemen"),
    (28, "flamininus", "Titus Flamininus"),
    (29, "philopoemen-flamininus", "Comparison of Philopoemen and Flamininus"),
    (30, "pyrrhus", "Pyrrhus"),
    (31, "marius", "Caius Marius"),
    (32, "lysander", "Lysander"),
    (33, "sulla", "Sulla"),
    (34, "lysander-sulla", "Comparison of Lysander and Sulla"),
    (35, "cimon", "Cimon"),
    (36, "lucullus", "Lucullus"),
    (37, "cimon-lucullus", "Comparison of Cimon and Lucullus"),
    (38, "nicias", "Nicias"),
    (39, "crassus", "Crassus"),
    (40, "nicias-crassus", "Comparison of Nicias and Crassus"),
    (41, "eumenes", "Eumenes"),
    (42, "sertorius", "Sertorius"),
    (43, "sertorius-eumenes", "Comparison of Sertorius and Eumenes"),
    (44, "agesilaus", "Agesilaus"),
    (45, "pompey", "Pompey"),
    (46, "agesilaus-pompey", "Comparison of Agesilaus and Pompey"),
    (47, "alexander", "Alexander"),
    (48, "caesar", "Caesar"),
    (49, "phocion", "Phocion"),
    (50, "cato-minor", "Cato the Younger"),
    (51, "agis-cleomenes", "Agis and Cleomenes"),
    (52, "gracchi", "Tiberius and Caius Gracchus"),
    (53, "agis-cleomenes-gracchi", "Comparison of Agis and Cleomenes with the Gracchi"),
    (54, "demosthenes", "Demosthenes"),
    (55, "cicero", "Cicero"),
    (56, "demosthenes-cicero", "Comparison of Demosthenes and Cicero"),
    (57, "demetrius", "Demetrius"),
    (58, "antony", "Antony"),
    (59, "demetrius-antony", "Comparison of Demetrius and Antony"),
    (60, "dion", "Dion"),
    (61, "brutus", "Brutus"),
    (62, "dion-brutus", "Comparison of Dion and Brutus"),
    (63, "aratus", "Aratus"),
    (64, "artaxerxes", "Artaxerxes"),
    (65, "galba", "Galba"),
    (66, "otho", "Otho"),
]
# the files' versions where they aren't grc2 and eng2: (Greek, English)
VERSIONS = {1: ("perseus-grc2", "perseus-eng3"), 51: ("perseus-grc1", "perseus-eng1"), 52: ("perseus-grc1", "perseus-eng1")}
# held out whole, each with its pair and their comparison: Pericles and Fabius Maximus, Timoleon and
# Aemilius Paulus
LIVES_HELD_OUT = {12, 13, 14, 18, 19, 20}
# where Perrin's Greek and English number a section differently: (Greek renames, English renames)
LIVES_RENAMES: dict[int, tuple[dict[str, str], dict[str, str]]] = {
    7: ({}, {"11.11": "11.1"}),  # Solon: the English's 11.11 for 11.1
    11: (
        {"6.4": "6.3"},
        {"38.4": "38.3"},
    ),  # Camillus: the English's 6.3 is the Greek's 6.3-4, the Greek's 38.3 the English's 38.3-4
    57: ({}, {"33.5": "33.4"}),  # Demetrius: the English's 33.5 for 33.4
}
LIVES = [
    Work(
        "lives",
        name,
        f"Plutarch, {title}",
        perseus(f"tlg0007.tlg{n:03d}", VERSIONS.get(n, ("perseus-grc2", "perseus-eng2"))[0]),
        (perseus(f"tlg0007.tlg{n:03d}", VERSIONS.get(n, ("perseus-grc2", "perseus-eng2"))[1]),),
        held_out="*" if n in LIVES_HELD_OUT else None,
        greek_renames=LIVES_RENAMES.get(n, ({}, {}))[0],
        english_renames=LIVES_RENAMES.get(n, ({}, {}))[1],
    )
    for n, name, title in LIVES_TABLE
]

# the sources' typos and stray marks, fixed in the cleaned text (sigla already removed) where each
# occurs exactly once:
# (work, ref, side, old, new)
ERRATA = [
    ("herodotus", "7.76.1", "eng", "<Pisidians>", "Pisidians"),
    ("thucydides", "1.29.4", "eng", "sail>(forty", "sail (forty"),
    ("thucydides", "1.29.4", "eng", "action,,", "action,"),
    ("anabasis", "5.7.28", "eng", "the cry `Pelt, pelt, that", "the cry 'Pelt, pelt,' that"),
    ("anabasis", "7.6.18", "eng", ">But it is far", "But it is far"),
    ("cyropaedia", "4.1.18", "grc", "ἰέναι. 1", "ἰέναι."),
    ("diogenes", "1.1.37", "grc", " ἐνάτης ?", ""),  # an editor's conjecture beside the reading (its brackets gone)
    ("diogenes", "1.2.60", "grc", "ἀργαλέω νμελεδωνέων", "ἀργαλέων μελεδωνέων"),
    ("diogenes", "1.2.60", "eng", "Mimnermus:>", "Mimnermus:"),
    ("diogenes", "4.3.20", "eng", "him:>", "him:"),
    ("diogenes", "7.1.14", "grc", "3μέσου", "μέσου"),
    ("diogenes", "8.2.76", "grc", "ἔχθει.>", "ἔχθει."),
    ("romulus", "8.7", "grc", " (FHG III 78)", ""),  # an editor's citation in the text
    ("alexander", "54.1", "grc", "ὁ ῝ Ἕρμιππός", "ὁ Ἕρμιππός"),
    ("demetrius", "36.4", "grc", "ϝεώτερα", "νεώτερα"),
    ("antony", "39.5", "grc", "sὁ δὲ", "ὁ δὲ"),
    ("antony", "67.4", "grc", "γυ˙ ναῖκες", "γυναῖκες"),
]

# the editions' sigla, removed from the Greek with their content kept: brackets for doubtful,
# supplied or deleted words ([ ], double brackets, the angle brackets of supplements), marks of
# lacunae (*, #), a stray rough-breathing quote mark and acute
GREEK_SIGLA = set("[]\u27e6\u27e7\u2329\u232a\u3008\u3009*#\u02bd\u00b4")
# in the English, the marks of lacunae (Hicks's * *); the translators' [ ] are their own words, kept
ENGLISH_SIGLA = set("*")
WORKS = HISTORIES + LIVES


# ---------------------------------------------------------------- sources


def fetch(path: str, expected: dict[str, str], cache: str | None) -> bytes:
    if path not in expected:
        sys.exit(f"{path}: not in sources.json")
    local = os.path.join(cache, path) if cache else None
    if local and os.path.exists(local):
        with open(local, "rb") as f:
            raw = f.read()
    else:
        request = urllib.request.Request(BASE_URL + path, headers={"User-Agent": "indrajala-datasets-perseus-parallel/clean.py"})
        with urllib.request.urlopen(request) as response:
            raw = response.read()
        if local:
            os.makedirs(os.path.dirname(local), exist_ok=True)
            with open(local, "wb") as f:
                f.write(raw)
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected[path]:
        sys.exit(f"{path} at {COMMIT[:7]}: sha256 is {actual}, expected {expected[path]}")
    return raw


# ---------------------------------------------------------------- the citation tree


@dataclass
class Node:
    n: str
    element: ET.Element
    children: dict[str, Node]


def is_textpart(element: ET.Element) -> bool:
    return element.tag == f"{TEI}div" and element.get("type") == "textpart"


def textparts(element: ET.Element) -> list[ET.Element]:
    """element's nearest textpart descendants (not inside another textpart)."""
    found = []
    for child in element:
        if is_textpart(child):
            found.append(child)
        elif child.tag not in DROPPED:
            found.extend(textparts(child))
    return found


def build(element: ET.Element, n: str, path: str) -> Node:
    children: dict[str, Node] = {}
    for child in textparts(element):
        key = (child.get("n") or "").strip()
        if not key:
            raise ValueError(f"{path}: a textpart without a number under {n}")
        if key in children:
            raise ValueError(f"{path}: textpart {n}.{key} occurs twice")
        children[key] = build(child, key, path)
    return Node(n, element, children)


def citation_tree(raw: bytes, path: str) -> Node:
    root = ET.fromstring(raw)
    body = root.find(f".//{TEI}body")
    if body is None:
        raise ValueError(f"{path}: no body")
    tops = [d for d in body.iter(f"{TEI}div") if d.get("type") in ("edition", "translation")]
    if len(tops) != 1:
        raise ValueError(f"{path}: {len(tops)} edition or translation divs, not 1")
    return build(tops[0], "", path)


def header_text(raw: bytes, tag: str) -> list[str]:
    root = ET.fromstring(raw)
    header = root.find(f"{TEI}teiHeader")
    if header is None:
        return []
    return [" ".join("".join(e.itertext()).split()) for e in header.iter(f"{TEI}{tag}")]


# ---------------------------------------------------------------- text


def flatten(element: ET.Element, in_choice: bool = False) -> str:
    parts = [element.text or ""]
    for child in element:
        tag = child.tag
        if tag in DROPPED or (tag == f"{TEI}reg" and not in_choice):
            pass
        elif tag == f"{TEI}choice":
            kept = [c for c in child if c.tag in CHOICE_KEPT]
            parts.append(" ".join(flatten(c, True) for c in kept) if kept else flatten(child, True))
        elif in_choice and tag in (f"{TEI}sic", f"{TEI}orig", f"{TEI}abbr"):
            pass
        elif tag in BREAKS:
            parts.append(" ")
        else:
            parts.append(flatten(child))
            if tag in BLOCKS:
                parts.append(" ")
        parts.append(child.tail or "")
    return "".join(parts)


def leaf_text(node: Node) -> str:
    return " ".join(flatten(node.element).split())


def outside_text(node: Node) -> str:
    """node's own text outside its child textparts: dropped when its children are paired."""
    if not node.children:
        return ""
    kept = {id(c.element) for c in node.children.values()}

    def walk(element: ET.Element) -> str:
        parts = [element.text or ""]
        for child in element:
            if id(child) in kept or child.tag in DROPPED:
                pass
            else:
                parts.append(walk(child))
            parts.append(child.tail or "")
        return "".join(parts)

    return " ".join(walk(node.element).split())


def is_greek(ch: str) -> bool:
    return "\u0370" <= ch <= "\u03ff" or "\u1f00" <= ch <= "\u1fff"


def english(text: str, where: str, unknown: Counter[str]) -> str | None:
    """text in ASCII; None when it quotes Greek (the pair is dropped and reported)."""
    out = []
    odd = []
    for ch in unicodedata.normalize("NFKD", text.replace(CRUX, " ")):
        if ch in ENGLISH_SIGLA:
            continue
        if ch.isascii():
            out.append(ch)
        elif unicodedata.combining(ch):
            pass
        elif ch in SPELLED:
            out.append(SPELLED[ch])
        else:
            odd.append(ch)
    if any(is_greek(ch) for ch in odd):
        return None
    for ch in odd:
        unknown[f"{ch!r} U+{ord(ch):04X} in {where}"] += 1
    return " ".join("".join(out).split())


def greek(text: str, stray: Counter[str]) -> str:
    """text in NFC, elisions unified, sigla removed; a combining mark NFC can't attach to its letter
    (a malformed character in the source) is dropped and counted."""
    out = []
    for ch in unicodedata.normalize("NFC", text.replace(CRUX, " ")):
        if ch in GREEK_SIGLA:
            continue
        if unicodedata.combining(ch):
            stray[ch] += 1
            continue
        out.append(ELISION.get(ch, ch))
    return " ".join("".join(out).split())


# ---------------------------------------------------------------- alignment


@dataclass
class Pair:
    work: str
    ref: str
    grc: str
    eng: str
    split: str = "train"


@dataclass
class Alignment:
    pairs: list[tuple[str, str, str]]  # (ref, Greek raw text, English raw text)
    unmatched: list[tuple[str, str, int]]  # (ref, side or reason, characters)
    outside: Counter[str]  # side -> characters outside the paired units
    joined: list[str] = field(default_factory=list)  # pairs joined where the sides' boundaries drift


def leaves(node: Node, ref: str, top: tuple[str, ...] | None, outside: Counter[str], side: str) -> list[tuple[str, Node]]:
    """node's deepest citation units, in order, with their refs; text outside them counted."""
    if not node.children:
        return [(ref, node)]
    outside[side] += len(outside_text(node))
    found = []
    for key, child in node.children.items():
        if top is not None and not ref and key not in top:
            continue
        found.extend(leaves(child, f"{ref}.{key}" if ref else key, None, outside, side))
    return found


def renumbered(units: list[tuple[str, Node]], renames: dict[str, str]) -> dict[str, str]:
    """ref -> text, with renames applied; units renamed to one ref are joined in order."""
    texts: dict[str, list[str]] = {}
    for ref, node in units:
        texts.setdefault(renames.get(ref, ref), []).append(leaf_text(node))
    unused = set(renames) - {ref for ref, _ in units}
    if unused:
        raise ValueError(f"renames of refs that don't occur: {sorted(unused)}")
    return {ref: " ".join(parts) for ref, parts in texts.items()}


def align_work(work: Work, greek_tree: Node, english_tree: Node) -> Alignment:
    """Pairs by ref, in the Greek's order; a unit one side divides and the other doesn't is an error
    (none here: a new source that does needs its own rule)."""
    out = Alignment([], [], Counter())
    g = renumbered(leaves(greek_tree, "", work.books, out.outside, "grc"), work.greek_renames)
    e = renumbered(leaves(english_tree, "", work.books, out.outside, "eng"), work.english_renames)
    for side, ours, theirs in (("grc", g, e), ("eng", e, g)):
        for ref in ours:
            if ref not in theirs and any(r.startswith(ref + ".") for r in theirs):
                raise ValueError(f"{work.name} {ref}: divided in one file, not in the other ({side} undivided)")
    for ref, text in g.items():
        if ref in e:
            out.pairs.append((ref, text, e[ref]))
        else:
            out.unmatched.append((ref, "grc", len(text)))
    out.unmatched.extend((ref, "eng", len(text)) for ref, text in e.items() if ref not in g)
    return out


def ratio_ok(grc: str, eng: str) -> bool:
    return bool(grc) and bool(eng) and 0.5 <= len(eng) / len(grc) <= 2.5


def outlier(p: Pair) -> bool:
    return min(len(p.grc), len(p.eng)) >= 20 and not ratio_ok(p.grc, p.eng)


def parent(ref: str) -> str:
    return ref.rsplit(".", 1)[0]


def merged(a: Pair, b: Pair) -> Pair:
    last = b.ref.rsplit(".", 1)[1].split("-")[-1]
    return Pair(a.work, f"{a.ref}-{last}", f"{a.grc} {b.grc}", f"{a.eng} {b.eng}", a.split)


def merge_drift(pairs: list[Pair]) -> tuple[list[Pair], list[str]]:
    """Where the two sides end a unit at different points, the neighbours trade text: a pair out of
    ratio is joined with its previous or next neighbour in the same chapter, whichever join is in
    ratio and nearer the work's median ratio. The joined pair's ref spans both ("3.16-17")."""
    if not pairs:
        return pairs, []
    median = statistics.median(math.log(len(p.eng) / len(p.grc)) for p in pairs)

    def distance(p: Pair) -> float:
        return abs(math.log(len(p.eng) / len(p.grc)) - median)

    out: list[Pair] = []
    joins: list[str] = []
    i = 0
    while i < len(pairs):
        p = pairs[i]
        if not outlier(p):
            out.append(p)
            i += 1
            continue
        options = []
        if out and parent(out[-1].ref) == parent(p.ref):
            options.append(("previous", merged(out[-1], p)))
        if i + 1 < len(pairs) and parent(pairs[i + 1].ref) == parent(p.ref):
            options.append(("next", merged(p, pairs[i + 1])))
        options = [(side, q) for side, q in options if ratio_ok(q.grc, q.eng)]
        if not options:
            out.append(p)
            i += 1
            continue
        side, q = min(options, key=lambda option: distance(option[1]))
        if side == "previous":
            if joins and joins[-1] == out[-1].ref:
                joins.pop()  # the previous pair was a join already: record the wider one
            out[-1] = q
            i += 1
        else:
            out.append(q)
            i += 2
        joins.append(q.ref)
    return out, joins


# ---------------------------------------------------------------- splits


def assign_splits(work: Work, pairs: list[Pair]) -> None:
    if work.held_out is None:
        return
    if work.held_out == "*":
        held = pairs
        unit = lambda p: p.ref.split(".")[0]
    else:
        held = [p for p in pairs if p.ref.split(".")[0] == work.held_out]
        unit = lambda p: p.ref.split(".")[1]
    if not held:
        raise ValueError(f"{work.name}: held-out unit {work.held_out} has no pairs")
    half = len(held) / 2
    split = "validation"
    previous = None
    for count, p in enumerate(held):
        u = unit(p)
        if u != previous and count >= half:
            split = "test"
        previous = u
        p.split = split


# ---------------------------------------------------------------- near-duplicates


def shingles(text: str, k: int = 8) -> set[str]:
    bare = "".join(c for c in unicodedata.normalize("NFD", text.lower()) if c.isalpha() and not unicodedata.combining(c))
    return {bare[i : i + k] for i in range(max(0, len(bare) - k + 1))}


def near_duplicates(pairs: list[Pair], threshold: float = 0.5) -> list[tuple[Pair, Pair, float]]:
    """held-out pairs whose Greek shares at least threshold of its 8-character shingles with a train pair's."""
    index: dict[str, list[int]] = defaultdict(list)
    train = [p for p in pairs if p.split == "train"]
    train_shingles = [shingles(p.grc) for p in train]
    for i, s in enumerate(train_shingles):
        for x in s:
            index[x].append(i)
    found = []
    for p in pairs:
        if p.split == "train":
            continue
        s = shingles(p.grc)
        if len(s) < 4:
            continue
        hits: Counter[int] = Counter()
        for x in s:
            for i in index.get(x, ()):
                hits[i] += 1
        if not hits:
            continue
        i, shared = hits.most_common(1)[0]
        score = shared / len(s)
        if score >= threshold:
            found.append((p, train[i], score))
    return found


# ---------------------------------------------------------------- the build


def build_all(cache: str | None) -> tuple[dict[str, list[Pair]], str]:
    with open(SOURCES) as f:
        expected = json.load(f)
    report: list[str] = []
    corpora: dict[str, list[Pair]] = {"histories": [], "lives": []}
    unknown: Counter[str] = Counter()
    stray: Counter[str] = Counter()
    errata: dict[tuple[str, str], list[tuple[str, str, str, str, str]]] = defaultdict(list)
    for erratum in ERRATA:
        errata[erratum[:2]].append(erratum)
    per_work: list[tuple[Work, str, Alignment, list[Pair]]] = []
    candidates_table: list[str] = []

    for work in WORKS:
        greek_raw = fetch(work.greek, expected, cache)
        greek_tree = citation_tree(greek_raw, work.greek)
        best = None
        for path in work.english:
            english_raw = fetch(path, expected, cache)
            alignment = align_work(work, greek_tree, citation_tree(english_raw, path))
            good = sum(ratio_ok(g, e) for _, g, e in alignment.pairs)
            translator = ", ".join(header_text(english_raw, "editor")[:1]) or "?"
            if len(work.english) > 1:
                candidates_table.append(
                    f"| {translator} | `{os.path.basename(path)}` | {len(alignment.pairs):,} | {good:,} | "
                    f"{len(alignment.unmatched):,} |"
                )
            if best is None or good > best[0]:
                best = (good, path, alignment, translator)
        assert best is not None
        _, path, alignment, translator = best
        pairs = []
        for ref, g, e in alignment.pairs:
            eng = english(e, f"{work.name} {ref}", unknown)
            if eng is None:
                alignment.unmatched.append((ref, "Greek in English", 0))
                continue
            pairs.append(Pair(work.name, ref, greek(g, stray), eng))
        for p in pairs:
            for erratum in errata.pop((work.name, p.ref), []):
                _, _, side, old, new = erratum
                text = getattr(p, side)
                if text.count(old) != 1:
                    raise ValueError(
                        f"an erratum's text occurs {text.count(old)} times in {work.name} {p.ref}, not once: {old!r}"
                    )
                setattr(p, side, text.replace(old, new))
        # a unit empty on a side after cleaning (a section of notes only, a verse an edition omits)
        alignment.unmatched.extend((p.ref, "empty", 0) for p in pairs if not (p.grc and p.eng))
        pairs = [p for p in pairs if p.grc and p.eng]
        pairs, joins = merge_drift(pairs)
        alignment.joined = joins
        assign_splits(work, pairs)
        corpora[work.corpus].extend(pairs)
        per_work.append((work, f"{translator} (`{os.path.basename(path)}`)", alignment, pairs))

    if errata:
        raise ValueError(f"errata for pairs that don't occur: {sorted(errata)}")
    if unknown:
        sys.exit("English characters NFKD doesn't reduce to ASCII: " + "\n".join(f"{c} x{n}" for c, n in sorted(unknown.items())))

    report.append(render_report(per_work, candidates_table, corpora, stray))
    return corpora, "\n".join(report)


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "-"


def render_report(per_work, candidates_table, corpora, stray) -> str:
    lines = [
        "# The alignment report",
        "",
        f"Built by `clean.py` from PerseusDL/canonical-greekLit at `{COMMIT}`. Lengths are in characters",
        "after cleaning (Greek in Unicode code points, NFC; English in ASCII).",
        "",
        "## Pairs by work",
        "",
        "| corpus | work | translation | pairs | train | validation | test | Greek chars | English chars | median Greek / English | longest Greek / English |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for work, translation, _, pairs in per_work:
        splits = Counter(p.split for p in pairs)
        gl = [len(p.grc) for p in pairs]
        el = [len(p.eng) for p in pairs]
        lines.append(
            f"| {work.corpus} | {work.title} | {translation} | {len(pairs):,} | {splits['train']:,} | "
            f"{splits['validation']:,} | {splits['test']:,} | {sum(gl):,} | {sum(el):,} | "
            f"{statistics.median(gl):.0f} / {statistics.median(el):.0f} | {max(gl):,} / {max(el):,} |"
        )
    lines += [
        "",
        "## Corpora",
        "",
        "| corpus | pairs | train | validation | test | Greek chars | English chars |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for corpus, pairs in corpora.items():
        splits = Counter(p.split for p in pairs)
        lines.append(
            f"| {corpus} | {len(pairs):,} | {splits['train']:,} | {splits['validation']:,} | {splits['test']:,} | "
            f"{sum(len(p.grc) for p in pairs):,} | {sum(len(p.eng) for p in pairs):,} |"
        )
    if candidates_table:
        lines += [
            "",
            "## Thucydides: the candidate translations",
            "",
            "Chosen: the most pairs whose English is 0.5 to 2.5 times the Greek's length (before joins).",
            "",
            "| translator | file | pairs | pairs in ratio | unmatched units |",
            "| --- | --- | ---: | ---: | ---: |",
        ] + candidates_table
    lines += [
        "",
        "## Windows",
        "",
        "Pairs whose Greek or English is longer than a window: a packed window drops them, never cuts them.",
        "",
        "| corpus | " + " | ".join(f"over {w}" for w in WINDOWS) + " |",
        "| --- | " + " | ".join("---:" for _ in WINDOWS) + " |",
    ]
    for corpus, pairs in corpora.items():
        cells = []
        for w in WINDOWS:
            over = sum(1 for p in pairs if max(len(p.grc), len(p.eng)) > w)
            cells.append(f"{over:,} ({pct(over, len(pairs))})")
        lines.append(f"| {corpus} | " + " | ".join(cells) + " |")
    lines += ["", f"### Over {WINDOWS[-1]}", ""]
    for corpus, pairs in corpora.items():
        over = [p for p in pairs if max(len(p.grc), len(p.eng)) > WINDOWS[-1]]
        lines.append(f"- {corpus}: " + (", ".join(f"{p.work} {p.ref} ({len(p.grc)}/{len(p.eng)})" for p in over) or "none"))
    lines += [
        "",
        "## What didn't align",
        "",
        "Units numbered on one side only (dropped), units empty on a side after cleaning (dropped), units",
        "whose English quotes Greek (dropped: Hicks's puns and etymologies), neighbours joined where the two",
        "sides end a unit at different points (an outlier of length ratio joined with its neighbour in the",
        "chapter when the join is in ratio), and text outside the paired units (dropped).",
        "",
        "| work | Greek only | English only | empty | English quotes Greek | joined | Greek chars outside | English chars outside |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    detail = []
    for work, _, alignment, _ in per_work:
        sides = Counter(side for _, side, _ in alignment.unmatched)
        lines.append(
            f"| {work.name} | {sides['grc']} | {sides['eng']} | {sides['empty']} | {sides['Greek in English']} | {len(alignment.joined)} | "
            f"{alignment.outside['grc']:,} | {alignment.outside['eng']:,} |"
        )
        if alignment.unmatched or alignment.joined:
            items = [f"{ref} ({side}{', ' + str(n) + ' chars' if n else ''})" for ref, side, n in alignment.unmatched]
            items += [f"{ref} (joined)" for ref in alignment.joined]
            detail.append(f"- {work.name}: " + ", ".join(items))
    lines += [""] + detail
    lines += [
        "",
        "## Length-ratio outliers",
        "",
        "Pairs whose English is under 0.5 or over 2.5 times the Greek's length, with both sides at least 20",
        "characters, that no join with a neighbour brings into ratio: kept, as boundary drift across more",
        "than two units, or a translation that adds or omits.",
        "",
    ]
    for corpus, pairs in corpora.items():
        odd = [p for p in pairs if outlier(p)]
        lines.append(
            f"- {corpus} ({len(odd)}): " + (", ".join(f"{p.work} {p.ref} ({len(p.grc)}/{len(p.eng)})" for p in odd) or "none")
        )
    lines += [
        "",
        "## Near-duplicates across the split",
        "",
        "Held-out pairs whose Greek shares at least half its 8-letter shingles (accents and case ignored)",
        "with a train pair's Greek.",
        "",
    ]
    for corpus, pairs in corpora.items():
        dups = near_duplicates(pairs)
        lines.append(
            f"- {corpus} ({len(dups)}): "
            + (", ".join(f"{a.work} {a.ref} ~ {b.work} {b.ref} ({s:.2f})" for a, b, s in dups) or "none")
        )
    lines += [
        "",
        "## Vocabularies",
        "",
        f"Stray combining marks dropped from the Greek (malformed characters in the sources): {sum(stray.values())}",
        "",
    ]
    for corpus, pairs in corpora.items():
        for side in ("grc", "eng"):
            chars = Counter("".join(getattr(p, side) for p in pairs))
            shown = "".join(sorted(chars))
            lines.append(
                f"- {corpus}, {'Greek' if side == 'grc' else 'English'}: {len(chars)} characters: `{shown.replace('`', '\\`')}`"
            )
    return "\n".join(lines) + "\n"


def serialise(pairs: list[Pair]) -> str:
    return "".join(
        json.dumps({"work": p.work, "ref": p.ref, "split": p.split, "grc": p.grc, "eng": p.eng}, ensure_ascii=False) + "\n"
        for p in pairs
    )


def file_metadata(corpus: str, path: str, text: str, pairs: list[Pair]) -> str:
    works: dict[str, Counter[str]] = {}
    for p in pairs:
        works.setdefault(p.work, Counter())[p.split] += 1
    meta = {
        "file": path,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "corpus": corpus,
        "format": "JSON Lines, UTF-8: one pair a line, {work, ref, split, grc, eng}, in text order",
        "pairs": len(pairs),
        "splits": dict(sorted(Counter(p.split for p in pairs).items())),
        "works": {name: dict(sorted(counts.items())) for name, counts in works.items()},
        "characters": {"grc": sum(len(p.grc) for p in pairs), "eng": sum(len(p.eng) for p in pairs)},
        "vocabulary": {
            "grc": "".join(sorted(set("".join(p.grc for p in pairs)))),
            "eng": "".join(sorted(set("".join(p.eng for p in pairs)))),
        },
        "longest": {"grc": max(len(p.grc) for p in pairs), "eng": max(len(p.eng) for p in pairs)},
    }
    return json.dumps(meta, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--check", action="store_true", help="compare with the committed files instead of writing them")
    parser.add_argument("--cache", help="keep the fetched sources in this directory")
    args = parser.parse_args()
    corpora, report = build_all(args.cache)
    outputs = {}
    for corpus, path in OUT.items():
        outputs[path] = serialise(corpora[corpus])
        outputs[path + ".metadata.json"] = file_metadata(corpus, path, outputs[path], corpora[corpus])
    outputs[REPORT] = report
    if args.check:
        bad = []
        for path, text in outputs.items():
            with open(os.path.join(HERE, path), encoding="utf-8") as f:
                if f.read() != text:
                    bad.append(path)
        if bad:
            sys.exit("differs from the committed file: " + ", ".join(bad))
        print("all files match")
        return
    for path, text in outputs.items():
        full = os.path.join(HERE, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    for corpus, pairs in corpora.items():
        print(f"{corpus}: {len(pairs):,} pairs")


if __name__ == "__main__":
    main()
