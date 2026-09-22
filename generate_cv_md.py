#!/usr/bin/env python3
"""Generate cv.md (a Jekyll-flavored Markdown/HTML CV) from the same
bib/*.bib files that drive SaundersAdam_CV.tex, so the publication lists in
both outputs stay in sync. The non-bibliography sections (Education,
Experience, Professional Outreach, Honors and Awards, Skills) are hand-
maintained below, mirroring the way they're hand-maintained directly in the
.tex file rather than pulled from a shared data source.

Run: python3 generate_cv_md.py
"""
import re

BIB_DIR = "bib"
OUT_PATH = "cv.md"


# --------------------------------------------------------------------------
# Minimal BibTeX parser, tailored to this repo's bib files: one entry per
# @type{key, ...}, fields as `name = {value},` with possible brace nesting
# inside a value (e.g. "{Ho Hin Lee*}" or "{\textbf{Adam M. Saunders}*}").
# --------------------------------------------------------------------------
def parse_bib(path):
    text = open(path, encoding="utf-8").read()
    entries = []
    i = 0
    while True:
        at = text.find("@", i)
        if at == -1:
            break
        brace = text.find("{", at)
        entrytype = text[at + 1 : brace].strip().lower()
        comma = text.find(",", brace)
        pos = comma + 1
        fields = {}
        while True:
            while pos < len(text) and text[pos] in " \t\n\r,":
                pos += 1
            if text[pos] == "}":
                pos += 1
                break
            eq = text.find("=", pos)
            fname = text[pos:eq].strip()
            pos = eq + 1
            while text[pos] in " \t\n":
                pos += 1
            assert text[pos] == "{", f"expected '{{' at {pos} in {path}"
            depth = 1
            start = pos + 1
            j = start
            while depth > 0:
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                j += 1
            fields[fname] = text[start : j - 1]
            pos = j
        entries.append({"type": entrytype, "fields": fields})
        i = pos
    return entries


# --------------------------------------------------------------------------
# LaTeX-ish field content -> Markdown
# --------------------------------------------------------------------------
def latex_to_md(s):
    if not s:
        return s
    s = re.sub(r"\\highlight\{(.*?)\}", r"**\1**", s)
    s = s.replace("\\&", "&").replace("\\_", "_").replace("\\%", "%")
    s = s.replace("\\textit{", "_").replace("\\textbf{", "**")
    # crude close-up for any \textit{...}/\textbf{...} left dangling above
    return s


def split_on_and(s):
    """Split an author-list string on top-level ' and ', respecting braces."""
    parts, buf, depth, i = [], "", 0, 0
    while i < len(s):
        c = s[i]
        if c == "{":
            depth += 1
            buf += c
        elif c == "}":
            depth -= 1
            buf += c
        elif depth == 0 and s[i : i + 5] == " and ":
            parts.append(buf)
            buf = ""
            i += 5
            continue
        else:
            buf += c
        i += 1
    if buf:
        parts.append(buf)
    return [p.strip() for p in parts]


def format_name(token):
    """One author token -> Markdown display name (bold if it's the CV owner,
    using __x__ instead of **x** right before a bare equal-contribution '*'
    so the trailing '\\*' doesn't collide with the bold delimiters)."""
    token = token.strip()
    if token.startswith("{") and token.endswith("}"):
        inner = token[1:-1]
        star = inner.endswith("*")
        if star:
            inner = inner[:-1]
        m = re.match(r"\\textbf\{(.*)\}$", inner)
        if m:
            name = m.group(1)
            return f"__{name}__\\*" if star else f"**{name}**"
        return f"{inner}\\*" if star else inner
    if "," in token:
        family, given = (p.strip() for p in token.split(",", 1))
        display = f"{given} {family}".strip()
    else:
        display = token
        family = token.split()[-1] if token.split() else token
    return f"**{display}**" if family == "Saunders" else display


def format_authors(author_field):
    names = [format_name(t) for t in split_on_and(author_field)]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + ", and " + names[-1]


def doi_link(doi):
    # Matches the PDF driver, which always prints "doi: <value>" verbatim
    # (even for arXiv's 10.48550/ DOI prefix) rather than relabeling it.
    return f"[doi: {doi}](https://doi.org/{doi})"


def format_entry(entry, status):
    f = entry["fields"]
    parts = []
    author_field = f.get("author")
    if author_field:
        authors_md = format_authors(author_field)
        if f.get("groupcredit"):
            authors_md += " " + latex_to_md(f["groupcredit"])
        parts.append(authors_md + ".")
    title = latex_to_md(f.get("title", "")).rstrip(".")
    if title:
        url = f.get("url")
        title_md = f"[{title}]({url})" if url else title
        parts.append(f"“{title_md}”.")
    year = f.get("year")
    doi = f.get("doi")
    note = f.get("note")
    prefix = {"accepted": "Accepted to", "submitted": "Submitted to"}.get(status)
    if entry["type"] == "article":
        # No volume/issue/page numbers -- matches the PDF, which dropped
        # them for the same "just venue and year" simplicity.
        journal = latex_to_md(f.get("journal", ""))
        venue_md = f"_{journal}_" if journal else ""
        if prefix:
            # An accepted/submitted journal article doesn't carry a real
            # publication year yet, so it's left off even when the .bib
            # data happens to already have one filled in.
            parts.append(f"{prefix} {venue_md}.")
        else:
            parts.append(f"{venue_md}, {year}.")
    else:  # inproceedings (conference papers, abstracts, talks)
        booktitle = latex_to_md(f.get("booktitle", ""))
        month = f.get("month")
        date = f"{month} {year}" if month and year else (year or "")
        # A conference's date is fixed regardless of review status, so
        # unlike journals it's kept even for an accepted/submitted entry.
        venue_clause = f"{booktitle}, {date}." if date else f"{booktitle}."
        parts.append(f"{prefix} {venue_clause}" if prefix else venue_clause)
    if doi:
        parts.append(doi_link(doi))
    if note:
        note_md = latex_to_md(note)
        if note_md.startswith("*") and not note_md.startswith("**"):
            note_md = "\\" + note_md
        parts.append(note_md)
    return " ".join(parts)


def sort_key(entry):
    try:
        return int(entry["fields"].get("year", 0))
    except ValueError:
        return 0


def render_section(status_files):
    """status_files: list of (path, status) in status-priority order
    (accepted, published, submitted) -- matching the PDF's own grouping.
    Entries within each status are sorted by year, descending."""
    lines = []
    for path, status in status_files:
        entries = sorted(parse_bib(f"{BIB_DIR}/{path}"), key=sort_key, reverse=True)
        for entry in entries:
            lines.append(f"* {format_entry(entry, status)}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


JOURNAL_FILES = [
    ("journal-accepted.bib", "accepted"),
    ("journal-published.bib", "published"),
    ("journal-submitted.bib", "submitted"),
]
CONFERENCE_FILES = [
    ("conference-accepted.bib", "accepted"),
    ("conference-published.bib", "published"),
    ("conference-submitted.bib", "submitted"),
]
ABSTRACT_FILES = [("abstracts.bib", "published")]
TALK_FILES = [("talks.bib", "published")]



def main():
    out = ["## Journal Publications", render_section(JOURNAL_FILES)]
    out += ["## Conference Papers", render_section(CONFERENCE_FILES)]
    out += ["## Abstracts and Short Papers", render_section(ABSTRACT_FILES)]
    out += ["## Talks", render_section(TALK_FILES)]
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out).rstrip() + "\n")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
