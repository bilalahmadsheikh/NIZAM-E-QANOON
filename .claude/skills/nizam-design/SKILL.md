---
name: nizam-design
description: The Nizam-e-Qanoon visual vocabulary — the stamp-paper palette (parchment, pine, brass, oxide), the Spectral and Karla pairing, dual script type scales, spacing and radius tokens, elevation, motion springs, and the premium component set. Load before writing any UI, choosing a colour, adding a component, or reviewing a screen, in Flutter or on the web.
---

# Nizam-e-Qanoon — design system

**Reference:** `docs/12-design-system.html`
**Intent:** Legal software defaults to navy, gold and a white page, and reads as institutional — which is exactly the feeling that stops people asking a legal question. This palette comes off the physical artefact instead.

## The direction: stamp paper

Pakistani judicial stamp paper is warm cream, printed in pine green, sealed in brass, numbered in oxide red. Four colours that already sit together and already mean something in this jurisdiction.

## Tokens — light

```
parchment  #F3EFE6   ground — NEVER white
card       #FBF8F1   surface
pine       #17352E   immersive field, primary button      11.6:1
brass      #B8873C   accent, fills, large type only
brass-deep #8A6216   accent as body text                   4.8:1
oxide      #A0392C   repealed, struck down, destructive    5.9:1
ink        #1A1F1C   text (green-biased black)            14.6:1
ink-2      #5A625C   secondary
ink-3      #8E958E   placeholders and icons only — never body text
rule       #DFD8C8   hairlines
```

## Tokens — dark is a different room, not the lights off

```
ground #121916   surface #1A2320   ink #EDE8DC
brass  #D4A557   ← becomes the PRIMARY accent (5.9:1)
oxide  #E0897B
```

Inverting a warm palette produces mud. Brass lifts on dark far better than green, so the identity survives the switch instead of going grey.

## Legal status — four values, colour never alone

| State | Mark | Rule |
|---|---|---|
| In force | ribbon seal, brass | The only state that is not a warning |
| Repealed | cross, oxide | Also struck down. Non-collapsible |
| Not in force | dashed edge, neutral | A dashed border does the work — no third hue |
| Amended | none, neutral | Deliberately calm. Amendment is ordinary |

## Type

- **Spectral** — statutory text, headings, explanations. Georgia falls back with close metrics.
- **Karla** — interface, labels, buttons, tab bar. **Never the text of a provision.**
- **IBM Plex Mono** — tokens, dates, identifiers.
- **Noto Nastaliq Urdu** — every Urdu run. No synthetic bold.

**The rule that carries the system: chrome is borrowed, content is ours.** Navigation uses a face that gets out of the way; statutory text uses one with a voice, so law reads like law rather than like an app.

Two scales, chosen **per run by script**, never per locale.

## Space is the luxury signal

```
ramp     4 8 12 16 24 32 44 64
gutter   24        card-pad 24        card-gap 16
target   48 min, 52 preferred
radius   10 chip · 14 control · 20 card · 28 sheet · 44 device
measure  38–44 ch for statutory text on a phone
```

**When in doubt, remove an element rather than shrink the gaps.** Half the information reads as twice the confidence; the same section packed tight reads as a database dump. Card padding is never 12 — that is the density trap.

Two elevation levels only: card and sheet. A third means the hierarchy is wrong, not that a shadow is missing.

## The premium details

- Primary buttons carry a **one-pixel inner highlight** and a shadow **tinted with their own hue rather than grey**. That is most of what separates a premium control from a coloured rectangle.
- 52 pt controls, not 44 — the minimum is a floor, not a target.
- Section numerals set large in brass anchor a provision screen.
- The deadline component uses the pine field with brass — urgency without alarm, because **red is reserved for law that no longer exists**.

## Motion — springs, never ease-in-out

Sheet 0.40/0.82 · push-pop 0.35/0.90 (interruptible by back-swipe) · press scale 0.97 · content in as opacity + 8 pt. Reduced motion collapses every one to a 120 ms fade. Never a spinner where a skeleton fits.

## Verify online before you claim

- **Google Fonts availability and weights** for Spectral, Karla and Noto Nastaliq Urdu before pinning a weight that may not exist.
- **Platform contrast and target guidance** (iOS HIG, Material, WCAG 2.2) when a threshold is in question — do not recall a ratio, look it up.
- Have a native Urdu reader check Nastaliq leading; 2.05 is a starting point, not a verified value.

## Common failures

- A white background. It kills the card elevation and makes every screen read as a form.
- Brass as body text on parchment — 2.8:1. Use `brass-deep`.
- Adding a fifth status colour. If a new state appears it gets a **shape**, not a hue.
- Setting statutory text in Karla, or interface labels in Spectral.
- Filling the screen because there is room.
