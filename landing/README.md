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

## "See the live dashboard" → the app

The nav "Live demo" link and the hero "See the live dashboard" button open the running
Sentinel app. The target is set in one place — `var APP_URL` in the `<script>` near the
bottom of `index.html`:

- **Local:** defaults to `http://localhost:8501`. Start the app with
  `python -m streamlit run sentinel_app.py` first, then the buttons open it in a new tab.
- **Deployed:** after hosting the app (e.g. free Streamlit Community Cloud → connect this
  repo, main file `sentinel_app.py`), paste the public URL into `APP_URL`. That's the
  full funnel: landing page → live demo → book-a-pilot form.

## "Book a pilot" lead-capture form

The page has a validated info-capture form (name, work email, role, facility, beds,
priority + consent). Out of the box it works with **no backend**: on submit it opens a
pre-filled email to `hello@sentinel.care` and shows a thank-you state.

To actually collect submissions in a database/inbox, set a form endpoint:

1. Create an endpoint (quickest: a free [Formspree](https://formspree.io) form, or your
   own backend that accepts a JSON `POST`).
2. In `index.html`, find `var FORM_ENDPOINT = "";` (in the `<script>` near the bottom)
   and paste your URL between the quotes, e.g.
   `var FORM_ENDPOINT = "https://formspree.io/f/abcdwxyz";`

With an endpoint set, submissions POST as JSON and the user sees the in-page thank-you;
on a network error they're prompted to email instead. Change the contact address by
find/replacing `hello@sentinel.care`.

## Honesty notes (kept in the page on purpose)
- The hero is labelled an **artist's concept**.
- Sentinel is described as a **wellbeing / early-warning aid, not a medical or
  emergency device**.
- Gait identification is framed as **"fairly accurately," improving over time, and
  supporting — not replacing — staff judgement**. Keep it that way; over-claiming
  biometric certainty is both a credibility and a compliance risk.
