// ESLint for the site's HTML and CSS. JavaScript is checked by oxlint (.oxlintrc.json).
// Both read what tools/lint_pages.py writes under .lint/: run `pnpm lint`.
import css from "@eslint/css";
import html from "@html-eslint/eslint-plugin";

// Every @html-eslint rule (correctness, accessibility, security) except these.
const HTML_OFF = [
  // layout and formatting: the pages are hand-formatted, and partly written by Python
  "indent", "attrs-newline", "element-newline", "require-closing-tags", "quotes", "lowercase",
  "no-extra-spacing-attrs", "no-extra-spacing-text", "no-trailing-spaces",
  "no-multiple-empty-lines", "sort-attrs", "class-spacing", "max-element-depth",
  // house style, not mistakes
  "id-naming-convention",          // the brief's ids are made from its headings
  "no-inline-styles",              // the map sets a few one-off styles inline
  "head-order",                    // a performance hint for big pages
  "require-explicit-size",         // the map frame's size comes from CSS
  // only for pages a search engine should list: the 404 and staged pages aren't
  "require-meta-description", "require-open-graph-protocol",
  // empty in the HTML, filled in by the page's script (the map's subtitle)
  "require-content",
  // browser-support rules: the site supports current browsers; see the CSS block below
  "use-baseline",
  // the legend's path icon: on phones the legend squeezes it, and with a viewBox its dashes
  // would shrink instead of being cropped as now (a visible change)
  "svg-require-viewbox",
  // these need a project-specific list to mean anything
  "no-restricted-attrs", "no-restricted-attr-values", "no-restricted-tags",
];

export default [
  {
    files: [".lint/pages/**/*.html"],
    ...html.configs["flat/all"],
    rules: {
      ...html.configs["flat/all"].rules,
      ...Object.fromEntries(HTML_OFF.map((r) => [`@html-eslint/${r}`, "off"])),
    },
  },
  {
    files: [".lint/css/**/*.css"],
    plugins: { css },
    language: "css/css",
    languageOptions: { tolerant: true },
    rules: {
      ...css.configs.recommended.rules,
      // flags only accent-color, which every current browser supports
      "css/use-baseline": "off",
    },
  },
];
