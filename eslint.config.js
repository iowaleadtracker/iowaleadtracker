// ESLint for the site's HTML and CSS. JavaScript is checked by oxlint (.oxlintrc.json).
// Both read what tools/lint_pages.py writes under .lint/: run `pnpm lint`.
import css from "@eslint/css";
import html from "@html-eslint/eslint-plugin";

export default [
  {
    files: [".lint/pages/**/*.html"],
    ...html.configs["flat/recommended"],
    rules: {
      ...html.configs["flat/recommended"].rules,
      // the pages are hand-formatted (and partly written by Python): no layout rules
      "@html-eslint/indent": "off",
      "@html-eslint/attrs-newline": "off",
      "@html-eslint/require-closing-tags": "off",
      "@html-eslint/no-extra-spacing-attrs": "off",
      "@html-eslint/quotes": "off",
      "@html-eslint/use-baseline": "off",
      "@html-eslint/element-newline": "off",
      "@html-eslint/no-extra-spacing-text": "off",
      "@html-eslint/no-trailing-spaces": "off",
      "@html-eslint/no-multiple-empty-lines": "off",
      // mistakes worth stopping
      "@html-eslint/no-duplicate-id": "error",
      "@html-eslint/no-duplicate-attrs": "error",
      "@html-eslint/no-duplicate-class": "error",
      "@html-eslint/no-ineffective-attrs": "error",
      "@html-eslint/no-target-blank": "error",
      "@html-eslint/require-button-type": "error",
      "@html-eslint/no-invalid-entity": "error",
      "@html-eslint/require-frame-title": "error",
    },
  },
  {
    files: [".lint/css/**/*.css"],
    plugins: { css },
    language: "css/css",
    languageOptions: { tolerant: true },
    rules: {
      ...css.configs.recommended.rules,
      "css/use-baseline": "off",
    },
  },
];
