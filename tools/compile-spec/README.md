# compile-spec

Compiles the seventeen documents in `docs/` into one volume,
`docs/00-complete-specification.html`.

```
python tools/compile-spec/build.py     # writes the volume
python tools/compile-spec/verify.py    # 17 checks, exit 1 on any failure
```

The volume is **generated**. Edit the source documents in `docs/` and recompile;
anything edited in `00-complete-specification.html` is lost on the next build.

## What it does

Each source document is a standalone page with its own stylesheet, and the
seventeen stylesheets are variants of one system that collide if merged
naively. So the compiler does not merge them — it isolates them.

| Step | Why |
|---|---|
| **Scope every rule** to `.p<part>` (`lib.scope_css`) | Seventeen `:root` blocks would otherwise flatten into one palette. Parts 12 and 13 use Stamp Paper; the rest use the Part 01 house style. Both survive. |
| **Namespace every id** to `d<part>-` (`lib.namespace_ids`) | `#arw`, `#f1t`, `#mandate` recur across documents. Rewrites `href`, `url(#)`, `xlink:href`, `aria-labelledby`, `aria-describedby`, `headers`. |
| **Label figures** with their part | Seventeen documents each start at "Figure 1". The original number is kept verbatim so in-prose references still resolve; `Doc 04 ·` is prepended for uniqueness. |
| **Anchor sections** | Sections that already carry a meaningful id (`#threat-model`) keep it; the rest get `d<part>-s<n>`. The contents register links to whichever ends up in the markup. |
| **Normalise the theme** (`build.normalize_theme`) | Seven documents guard dark tokens with a bare `:root` and carry no `[data-theme="dark"]` rule, so they would render the wrong theme mid-volume. The full three-state contract is synthesised from each document's own dark tokens. |

## Two invariants of the compiler itself

1. **A part's stylesheet must never reach the volume's chrome.** The part scope
   class sits on an inner `.pbody`, never on the `<article>`, so the part
   divider above it is out of reach. Without this, a document's `.dek` or
   `.meta` rule restyles the divider — Part 12 renders its dek in cream, which
   on the shell ground is invisible.

2. **Part identifiers are the original document numbers** (`01`, `03a`, `09b`),
   never a 1..17 renumbering. Those numbers are the project's citation scheme:
   a reference to `docs/03 §2.3` has to keep resolving after the merge.

## Adding or reordering a document

Edit `PARTS` in `build.py` — `(id, filename, title, role, summary, band)` —
and `BANDS` if the grouping changes. Then rebuild and run `verify.py`.

A new document must render inside a single `<div class="wrap">` and use only
`@media` at-rules; `verify.py` catches the rest.
