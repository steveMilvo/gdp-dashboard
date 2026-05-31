# Sentinel landing page

A self-contained marketing landing page — no build step, no dependencies.

## View it
Open `landing/index.html` in any browser (double-click it), or serve it:

```
cd landing
python -m http.server 8080      # then open http://localhost:8080
```

## Add the hero image
The page expects the concept render at:

```
landing/assets/hero.png
```

Save your image there (PNG or JPG — if you use `.jpg`, update the `<img src>` in
`index.html`). If the file is missing, the page shows a placeholder box instead of
breaking.

## Honesty notes (kept in the page on purpose)
- The hero is labelled an **artist's concept**.
- Sentinel is described as a **wellbeing / early-warning aid, not a medical or
  emergency device**.
- Gait identification is framed as **"fairly accurately," improving over time, and
  supporting — not replacing — staff judgement**. Keep it that way; over-claiming
  biometric certainty is both a credibility and a compliance risk.
