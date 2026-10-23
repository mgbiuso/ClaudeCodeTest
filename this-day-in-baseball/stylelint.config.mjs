// Stylelint settings for style.css. Built-in rules only, so nothing extra to install.
// "warning" means it is reported but does not count as a failure.
export default {
  rules: {
    "block-no-empty": true,
    "color-no-invalid-hex": true,
    "declaration-block-no-duplicate-properties": [true, { ignore: ["consecutive-duplicates-with-different-values"] }],
    "no-duplicate-selectors": [true, { severity: "warning" }],
    "property-no-unknown": true,
    "unit-no-unknown": true,
    "function-no-unknown": true,
    "selector-pseudo-class-no-unknown": true,
    "selector-pseudo-element-no-unknown": true,
    "font-family-no-duplicate-names": true,
    "no-invalid-double-slash-comments": true,
  },
};
