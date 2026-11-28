"""The CSS the landing page and the monitor-placement brief share.

Both pages put ``BASE_CSS`` at the top of their ``<style>``, then their own rules, which
use the same color variables. The map pages (template.html) and the staged and 404 pages
have their own styles.
"""

from __future__ import annotations

#: The site's colors, named by color rather than by use: several have more than one use
#: (silver is both the table rules and the header's secondary text).
#: Left as literals on purpose: plain white (#fff), the day note's near-black text
#: (#1d1d1b, used once), and the <meta name="theme-color"> values, which can't use CSS
#: variables: keep those equal to --ink by hand.
PALETTE = """\
  :root {
    --ink: #1f2933;     /* text, the header bar */
    --paper: #f5f7fa;   /* the page, text on the header bar */
    --gray: #52606d;    /* secondary text, borders on the header bar */
    --silver: #cbd2d9;  /* table rules, secondary text on the header bar */
    --mist: #eef1f4;    /* code and note backgrounds */
    --blue: #0b5cad;    /* links */
    --sky: #9fd3ff;     /* links on the header bar */
    --peach: #fde8c8;   /* warnings */
  }"""

#: Rules both pages use, in the order both had them.
BASE_CSS = (
    PALETTE
    + """
  html, body { margin: 0; font: 14px system-ui, -apple-system, sans-serif;
               background: var(--paper); color: var(--ink); }
  header { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px;
           padding: 8px 16px; background: var(--ink); color: var(--paper); }
  header .title { display: flex; flex-direction: column; }
  header .title p { margin: 0; font-size: 13px; color: var(--silver); }
  header .warn { margin: 0; flex-basis: 100%; color: var(--peach); font-size: 12.5px;
                 line-height: 1.4; }
  header .warn b { color: #fff; }
  .doc { max-width: 46rem; margin: 0 auto; padding: 24px 16px 48px; line-height: 1.55; }
  .doc h3 { font-size: 16px; margin: 20px 0 6px; }
  .doc p { margin: 0 0 10px; }
  .doc a { color: var(--blue); overflow-wrap: anywhere; } /* long source URLs wrap on phones */
  .tablewrap { overflow-x: auto; }
  .doc table { border-collapse: collapse; margin: 6px 0 10px; font-size: 13.5px; }
  .doc th, .doc td { border-bottom: 1px solid var(--silver); padding: 5px 10px 5px 0;
                     text-align: left; vertical-align: top; }
  @media (max-width: 600px) {
    header { gap: 6px 10px; padding: 6px 12px; }
  }"""
)
