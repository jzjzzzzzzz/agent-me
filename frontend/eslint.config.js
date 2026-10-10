import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";
export default tseslint.config({ignores:["dist","test-results","playwright-report"]},js.configs.recommended,...tseslint.configs.recommended,{files:["e2e/**/*.mjs","playwright.config.ts"],languageOptions:{globals:globals.node}},{files:["**/*.{ts,tsx}"],languageOptions:{ecmaVersion:2020,globals:globals.browser},plugins:{"react-hooks":reactHooks,"react-refresh":reactRefresh},rules:{...reactHooks.configs.recommended.rules,"react-refresh/only-export-components":["warn",{allowConstantExport:true}]}});
