import "@testing-library/jest-dom/vitest";

/**
 * Global Vitest setup for tests/front/ (mirrors krtr/front/src/, per D2).
 *
 * Registers jest-dom's matchers (toBeInTheDocument, etc.) for every test in
 * this tree, so individual test files don't each import it themselves.
 */
