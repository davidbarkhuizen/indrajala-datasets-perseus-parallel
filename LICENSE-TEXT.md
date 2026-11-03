# The texts' licence

`data/histories.jsonl` and `data/lives.jsonl` are adapted from the Perseus Digital
Library's TEI texts, the files `sources.json` lists at commit
`70427323b61267cdcd0256b9b02009c23392de07` of https://github.com/PerseusDL/canonical-greekLit.
Perseus releases them under the Creative Commons Attribution-ShareAlike 4.0 International licence
(CC BY-SA 4.0, https://creativecommons.org/licenses/by-sa/4.0/): most files state it in their
header, and the repository's README states it for all contents "unless otherwise indicated" (the
Herodotus files state no licence of their own).

The adapted texts are released under the same licence: CC BY-SA 4.0. Attribution: the Perseus
Digital Library, Tufts University (Gregory Crane, editor in chief), with the editions and
translations below. Changes: the TEI markup, notes, headings, bibliographic references, figures,
rejected readings, Perseus's place-name glosses, the editors' sigla and cruxes removed; units
aligned by citation, renumbered or joined where the two files differ, and split; typos corrected;
the English normalised to ASCII, the Greek to Unicode NFC. `clean.py` in this repository makes
every change, and its docstring and comments list them.

## The copyright check, per volume

Checked 2026-11-03 for the United States (where works published before 1931 are in the public
domain) and for terms of the author's life plus 50 or 70 years. The ancient texts themselves are
in the public domain everywhere.

### Translations

| work | translation | published | translator | United States | life + 70 |
| --- | --- | --- | --- | --- | --- |
| Herodotus | A. D. Godley, Loeb | 1920-25 | died 1925 | public domain | public domain |
| Thucydides | Richard Crawley | 1874 (Dent, 1914) | died 1893 | public domain | public domain |
| Xenophon, *Hellenica* | C. L. Brownson, Loeb vols. I-II | 1918-21 | died 1948 | public domain | public domain (since 2019) |
| Xenophon, *Anabasis* | C. L. Brownson, Loeb vols. II-III | 1921-22 | died 1948 | public domain | public domain (since 2019) |
| Xenophon, *Cyropaedia* | Walter Miller, Loeb vols. V-VI | 1914 | died 1949 | public domain | public domain (since 2020) |
| Diogenes Laertius | R. D. Hicks, Loeb | 1925 | died 1929 | public domain | public domain |
| Plutarch, *Parallel Lives* | Bernadotte Perrin, Loeb vols. I-XI | 1914-26 | died 1920 | public domain | public domain |

**Not included:** Pausanias, whose Loeb translation (W. H. S. Jones, died 1963, and H. A. Ormerod,
died 1964) is in the public domain in the United States for its volumes of 1918 and 1926, but
under terms of life plus 70 years only from 2034 and 2035; its later volumes (1933, 1935) were not
checked. The first tag, `v2026-11-03`, held its Books 1-5; they were dropped at `v2026-11-03.1`.

### Greek editions

| work | edition | published | editor |
| --- | --- | --- | --- |
| Herodotus | A. D. Godley, Loeb | 1920-25 | died 1925 |
| Thucydides | H. Stuart Jones, Oxford Classical Texts | 1900-01 (Perseus: the printings of 1910 and 1942, the latter with J. E. Powell's revised apparatus) | died 1939 |
| Xenophon | E. C. Marchant, Oxford Classical Texts | 1900-10 (Perseus: reprints of 1961-70) | died 1960 |
| Diogenes Laertius | R. D. Hicks, Loeb | 1925 | died 1929 |
| Plutarch, *Parallel Lives* | Bernadotte Perrin, Loeb | 1914-26 | died 1920 |

The Greek is an ancient text, reconstructed by its editors. Where a critical edition has its own
protection, the term is short and counted from publication: 25 years in Germany (§ 70 UrhG) and up
to 30 years in the European Union (Directive 2006/116/EC, art. 5), and 25 years for a typographical
arrangement in the United Kingdom. Every edition here, reprints included, is past those terms.
Only the text is used: none of the editions' apparatus, notes or prefaces.
