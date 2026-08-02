(() => {
  const TOKEN_KEY = "forgeos-token";
  const DEFAULT_TIMEOUT_MS = 15000;

  class ApiError extends Error {
    constructor(message, status = 0, details = null) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.details = details;
    }
  }

  function validationMessage(detail) {
    if (!Array.isArray(detail)) return typeof detail === "string" ? detail : null;
    return detail.map((item) => {
      const location = Array.isArray(item.loc) ? item.loc.filter((part) => part !== "body").join(".") : "";
      return location ? `${location}: ${item.msg}` : item.msg;
    }).filter(Boolean).join("; ");
  }

  function statusMessage(status, detail) {
    const validation = validationMessage(detail);
    if (validation) return validation;
    if (status === 401) return "Your session expired. Please log in again.";
    if (status === 403) return "You do not have permission to access this resource.";
    if (status === 404) return "The requested resource was not found.";
    if (status === 400 || status === 422) return "The request contains invalid data.";
    if (status >= 500) return "The ForgeOS server encountered an error. Please retry.";
    return `Request failed with status ${status}.`;
  }

  async function request(path, options = {}) {
    const controller = new AbortController();
    const { timeoutMs = DEFAULT_TIMEOUT_MS, ...fetchOptions } = options;
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    const headers = new Headers(fetchOptions.headers || {});
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const baseUrl = window.FORGEOS_API_BASE || window.location.origin;
    const url = new URL(path, baseUrl);

    try {
      const response = await fetch(url, {
        ...fetchOptions,
        headers,
        signal: controller.signal,
        credentials: "same-origin",
      });
      let body = null;
      if (response.status !== 204) {
        const contentType = response.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
          try {
            body = await response.json();
          } catch (_) {
            throw new ApiError("The server returned invalid JSON.", response.status);
          }
        } else {
          body = await response.text();
        }
      }
      if (!response.ok) {
        const detail = body && typeof body === "object" ? body.detail : body;
        if (response.status === 401 && !path.includes("/auth/login")) {
          localStorage.removeItem(TOKEN_KEY);
          window.dispatchEvent(new CustomEvent("forge:auth-expired"));
        }
        throw new ApiError(statusMessage(response.status, detail), response.status, detail);
      }
      return body;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (error.name === "AbortError") {
        throw new ApiError("The ForgeOS server did not respond in time. Please retry.");
      }
      throw new ApiError("Unable to reach the ForgeOS server. Check the server address and network connection.");
    } finally {
      clearTimeout(timeout);
    }
  }

  async function download(path, filename) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
    const headers = new Headers();
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    try {
      const response = await fetch(new URL(path, window.FORGEOS_API_BASE || window.location.origin), {
        headers,
        signal: controller.signal,
        credentials: "same-origin",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        if (response.status === 401) {
          localStorage.removeItem(TOKEN_KEY);
          window.dispatchEvent(new CustomEvent("forge:auth-expired"));
        }
        throw new ApiError(statusMessage(response.status, body?.detail), response.status, body?.detail);
      }
      const blob = await response.blob();
      const href = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(href);
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (error.name === "AbortError") throw new ApiError("The download timed out. Please retry.");
      throw new ApiError("Unable to download from the ForgeOS server.");
    } finally {
      clearTimeout(timeout);
    }
  }

  window.forgeApi = { request, download, ApiError };
})();
