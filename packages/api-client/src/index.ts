import type { Media, Job } from "../../shared-types/src";
export * from "../../shared-types/src";
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}
export function csrf() {
  return (
    document.cookie
      .split("; ")
      .find((v) => v.startsWith("lumvia_csrf="))
      ?.split("=")
      .slice(1)
      .join("=") ?? ""
  );
}
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (init.method && !["GET", "HEAD"].includes(init.method))
    headers.set("X-CSRF-Token", csrf());
  let response: Response;
  try {
    response = await fetch("/api/v1" + path, {
      ...init,
      headers,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ApiError(
      0,
      "NETWORK_ERROR",
      "接続が途切れました。少し待ってからもう一度お試しください。",
    );
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (
      response.status === 401 &&
      path !== "/auth/login" &&
      path !== "/auth/me"
    )
      window.dispatchEvent(new CustomEvent("lumvia:unauthorized"));
    throw new ApiError(
      response.status,
      data.error?.code ?? "REQUEST_FAILED",
      data.error?.message ?? "接続を確認して、もう一度お試しください。",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export function upload(
  file: File,
  batch: string,
  onProgress: (value: number) => void,
  signal?: AbortSignal,
  destination: Record<string, string> = {},
): Promise<Media> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/v1/media");
    xhr.setRequestHeader("X-CSRF-Token", csrf());
    xhr.setRequestHeader("Idempotency-Key", crypto.randomUUID());
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable)
        onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      const data = JSON.parse(xhr.responseText || "{}");
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else reject(new Error(data.error?.message ?? "追加できませんでした。"));
    };
    xhr.onerror = () =>
      reject(new Error("通信が途切れました。接続を確認してください。"));
    xhr.onabort = () => reject(new Error("アップロードをキャンセルしました。"));
    signal?.addEventListener("abort", () => xhr.abort(), { once: true });
    const form = new FormData();
    form.append("file", file);
    form.append("batch_id", batch);
    for (const [key, value] of Object.entries(destination))
      form.append(key, value);
    xhr.send(form);
  });
}
export function time(ms: number, precise = false) {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  return `${h ? `${h}:` : ""}${String(Math.floor(s / 60) % 60).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}${precise ? "." + String(Math.round(ms) % 1000).padStart(3, "0") : ""}`;
}
export function bytes(value: number) {
  return value >= 1024 ** 3
    ? `${(value / 1024 ** 3).toFixed(1)} GB`
    : `${(value / 1024 ** 2).toFixed(1)} MB`;
}
export function date(value: string) {
  return new Date(value).toLocaleDateString("ja-JP", {
    month: "short",
    day: "numeric",
  });
}
export const activeJob = (j: Job) =>
  ["PENDING", "QUEUED", "RUNNING", "RETRYING", "CANCEL_REQUESTED"].includes(
    j.state,
  );
export const jobLabel: Record<string, string> = {
  PENDING: "順番待ち",
  QUEUED: "順番待ち",
  RUNNING: "処理中",
  RETRYING: "再試行中",
  CANCEL_REQUESTED: "停止しています",
  COMPLETED: "完了",
  FAILED: "失敗",
  CANCELLED: "キャンセル済み",
  TIMED_OUT: "時間切れ",
};
