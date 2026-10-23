// ESLint settings for the site's JavaScript (plain browser scripts, no build step).
// index.html loads more.js first and app.js second, and the two share some names.
// The "shared" lists below tell ESLint about those names so it does not call them mistakes.
// If you add a new shared function between the two files, add its name to the right list.
const read = (names) => Object.fromEntries(names.map((n) => [n, "readonly"]));

const browser = read([
  "window", "document", "fetch", "localStorage", "sessionStorage", "navigator", "location", "history",
  "console", "setTimeout", "clearTimeout", "setInterval", "clearInterval", "requestAnimationFrame",
  "URL", "URLSearchParams", "IntersectionObserver", "Image", "Option", "Intl", "AbortController", "Event",
]);

const rules = {
  "no-undef": "error",
  "no-redeclare": "error",
  "no-unused-vars": ["warn", { vars: "local", caughtErrors: "none" }],
  "no-eval": "error",
  "no-implied-eval": "error",
  "no-dupe-keys": "error",
  "no-unreachable": "warn",
  "no-var": "warn",
  "prefer-const": "warn",
  "eqeqeq": ["warn", "smart"],
};

export default [
  {
    files: ["more.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      // Names more.js borrows from app.js.
      globals: { ...browser, ...read(["el", "svg", "barChart", "MONTHS"]) },
    },
    rules,
  },
  {
    files: ["app.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      // Names app.js borrows from more.js.
      globals: { ...browser, ...read(["teamBand", "moreBlocks", "negroBand"]) },
    },
    rules,
  },
];
