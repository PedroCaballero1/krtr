import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

/**
 * ESLint flat config for the frontend.
 *
 * Lives at the repo root (not inside krtr/front/) so its base path covers
 * both krtr/front/src/ and tests/front/, which mirrors it 1:1 outside the
 * package itself (D2). Named `.mjs` so Node treats it as ESM regardless of
 * the repo root's own (Python-focused) package.json.
 */
export default tseslint.config(
  { ignores: ["krtr/front/dist", "**/node_modules"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["krtr/front/src/**/*.{ts,tsx}", "tests/front/**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
    },
  },
  prettier,
);
