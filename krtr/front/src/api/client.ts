import i18n from "@/i18n/config";

/** The `{error, message_key}` shape every krtr-web error response uses (§3.4). */
export interface ApiErrorBody {
  error: string;
  message_key: string;
}

/** Thrown by `apiFetch` for any non-2xx response, with an already-translated message. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** DOM events `apiFetch` dispatches on `window`, for UI components to react to. */
export const ApiEvent = {
  Unauthorized: "krtr:api:unauthorized",
  RateLimited: "krtr:api:rate-limited",
} as const;

const CSRF_COOKIE_NAME = "__Host-krtr_csrf";
const CSRF_HEADER_NAME = "X-KRTR-CSRF";
const STATE_CHANGING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const UNKNOWN_ERROR_CODE = "unknown_error";

/**
 * Reads the CSRF cookie's raw value, if present.
 *
 * Exists so `apiFetch` can implement the double-submit pattern (task 4.5): the
 * cookie is readable by JS by design, so its value is echoed back as a
 * header the server compares it against.
 *
 * @returns The cookie's decoded value, or null if it isn't set.
 */
function readCsrfCookie(): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${CSRF_COOKIE_NAME}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

/**
 * Builds the request headers for one `apiFetch` call.
 *
 * @param method - The HTTP method, used to decide whether CSRF applies.
 * @param init - The caller-supplied headers, if any.
 * @returns Headers with the CSRF header added for state-changing methods.
 */
function buildHeaders(method: string, init?: HeadersInit): Headers {
  const headers = new Headers(init);
  if (STATE_CHANGING_METHODS.has(method.toUpperCase())) {
    const csrfToken = readCsrfCookie();
    if (csrfToken) {
      headers.set(CSRF_HEADER_NAME, csrfToken);
    }
  }
  return headers;
}

/**
 * Parses a failed response's `{error, message_key}` body, if present.
 *
 * @param response - The response to parse (read via `clone`, so the
 *   original body is still available to the caller).
 * @returns The parsed body, or null if it doesn't match the expected shape.
 */
async function parseErrorBody(response: Response): Promise<ApiErrorBody | null> {
  try {
    const body: unknown = await response.clone().json();
    const hasMessageKey =
      typeof body === "object" &&
      body !== null &&
      typeof (body as ApiErrorBody).message_key === "string";
    return hasMessageKey ? (body as ApiErrorBody) : null;
  } catch {
    return null;
  }
}

/**
 * Performs a same-origin `fetch`, adding CSRF, 401/429 handling and
 * translated errors.
 *
 * Exists as the one place the frontend talks to the backend (§3.4), so
 * every caller gets the same session/CSRF/error behavior instead of each
 * one reimplementing it.
 *
 * @param path - The same-origin path to request (e.g. `/api/cases`).
 * @param init - Standard `fetch` options; `credentials` is always overridden.
 * @returns The response, once it is known to be a 2xx.
 * @throws ApiError - For any non-2xx response, with `message` translated
 *   from the body's `message_key` when present.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const method = init.method ?? "GET";
  const response = await fetch(path, {
    ...init,
    method,
    credentials: "same-origin",
    headers: buildHeaders(method, init.headers),
  });

  if (response.status === 401) {
    window.dispatchEvent(new Event(ApiEvent.Unauthorized));
    window.location.assign("/");
  }
  if (response.status === 429) {
    window.dispatchEvent(new Event(ApiEvent.RateLimited));
  }
  if (!response.ok) {
    const body = await parseErrorBody(response);
    const message = body ? i18n.t(body.message_key) : response.statusText;
    throw new ApiError(response.status, body?.error ?? UNKNOWN_ERROR_CODE, message);
  }
  return response;
}
