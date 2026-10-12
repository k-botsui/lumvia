import { linkPage } from "./link-list-page.mjs";

const MAX_BYTES = 45000;
const TTL = 7 * 86400000;
export const reply = (status, value) =>
  Response.json(value, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
const error = (status, code, message) =>
  reply(status, { error: { code, message } });
const repositoryValid = (value) =>
  /^[A-Za-z0-9][A-Za-z0-9-]{0,38}\/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$/.test(
    value ?? "",
  );

export function parseMessage(data) {
  if (
    !data ||
    typeof data !== "object" ||
    Array.isArray(data) ||
    Object.keys(data).some(
      (k) => !["request_id", "subject", "body"].includes(k),
    )
  )
    return null;
  if (
    typeof data.request_id !== "string" ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      data.request_id,
    )
  )
    return null;
  if (typeof data.subject !== "string" || typeof data.body !== "string")
    return null;
  const subject = data.subject.trim(),
    body = data.body.trim();
  if (
    !subject ||
    subject.length > 200 ||
    /[\r\n\x00]/.test(subject) ||
    !body ||
    body.length > 10000 ||
    body.includes("\x00")
  )
    return null;
  return { request_id: data.request_id.toLowerCase(), subject, body };
}

async function boundedJson(request) {
  if (
    !request.headers
      .get("content-type")
      ?.toLowerCase()
      .startsWith("application/json")
  )
    return null;
  if (Number(request.headers.get("content-length")) > MAX_BYTES) return null;
  const reader = request.body?.getReader();
  if (!reader) return null;
  const chunks = [];
  let bytes = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    bytes += value.length;
    if (bytes > MAX_BYTES) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const output = new Uint8Array(bytes);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.length;
  }
  try {
    return JSON.parse(new TextDecoder().decode(output));
  } catch {
    return null;
  }
}

async function digest(secret, value) {
  const encode = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encode.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return [
    ...new Uint8Array(
      await crypto.subtle.sign("HMAC", key, encode.encode(value)),
    ),
  ]
    .map((x) => x.toString(16).padStart(2, "0"))
    .join("");
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET") {
      const asset = linkPage(url.pathname);
      if (asset) return asset;
    }
    if (!repositoryValid(env.GITHUB_REPOSITORY))
      return error(503, "SUPPORT_DISABLED", "問い合わせ窓口は準備中です。");
    if (request.method === "GET" && url.pathname === "/status") {
      let can_submit = false;
      let availability = "not_configured";
      if (env.GITHUB_TOKEN) {
        try {
          const response = await fetch(
            `https://api.github.com/repos/${env.GITHUB_REPOSITORY}/issues?per_page=1`,
            {
              redirect: "manual",
              signal: AbortSignal.timeout(8000),
              headers: {
                Authorization: `Bearer ${env.GITHUB_TOKEN.trim()}`,
                Accept: "application/vnd.github+json",
                "User-Agent": "Lumvia-Support",
              },
            },
          );
          can_submit = response.ok;
          availability = response.ok
            ? "ready"
            : response.status === 401
              ? "invalid_token"
              : response.status === 403 || response.status === 404
                ? "repository_access_denied"
                : "github_unavailable";
          await response.body?.cancel();
        } catch (failure) {
          availability =
            failure instanceof TypeError
              ? "invalid_token_or_request"
              : "github_unavailable";
          // Return availability only, never expose credentials or upstream data.
        }
      }
      return reply(200, {
        repository: env.GITHUB_REPOSITORY,
        can_submit,
        availability,
      });
    }
    if (request.method !== "POST" || url.pathname !== "/issues")
      return error(404, "NOT_FOUND", "この窓口はお問い合わせ専用です。");
    if (!env.GITHUB_TOKEN)
      return error(503, "SUPPORT_DISABLED", "問い合わせ窓口は準備中です。");
    const data = parseMessage(await boundedJson(request));
    if (!data)
      return error(422, "INVALID_MESSAGE", "件名と内容を確認してください。");
    const id = env.INBOX.idFromName("lumvia-public-support-v1");
    // Preserve Cloudflare's connection IP only internally, never accept an app-supplied identity.
    const headers = {
      "Content-Type": "application/json",
      "x-client-ip": request.headers.get("CF-Connecting-IP") || "unknown",
    };
    return env.INBOX.get(id).fetch(
      new Request("https://inbox/submit", {
        method: "POST",
        headers,
        body: JSON.stringify(data),
      }),
    );
  },
};

export class SupportInbox {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
  }
  async fetch(request) {
    const data = parseMessage(await request.json());
    if (!data)
      return error(422, "INVALID_MESSAGE", "件名と内容を確認してください。");
    const now = Date.now(),
      day = new Date(now).toISOString().slice(0, 10),
      hour = Math.floor(now / 3600000);
    const fingerprint = await digest(
      this.env.GITHUB_TOKEN,
      JSON.stringify([this.env.GITHUB_REPOSITORY, data.subject, data.body]),
    );
    const ipHash = await digest(
      this.env.GITHUB_TOKEN,
      `${day}:${request.headers.get("x-client-ip")}`,
    );
    const key = `receipt:${data.request_id}`,
      ipKey = `limit:${hour}:${ipHash}`,
      globalKey = `daily:${day}`;
    const reservation = await this.ctx.storage.transaction(async (tx) => {
      const existing = await tx.get(key);
      if (existing) return { existing };
      const ip = await tx.get(ipKey),
        total = await tx.get(globalKey);
      if ((ip?.count ?? 0) >= 3 || (total?.count ?? 0) >= 50)
        return { limited: true };
      await tx.put(ipKey, {
        count: (ip?.count ?? 0) + 1,
        expires_at: now + 86400000,
      });
      await tx.put(globalKey, {
        count: (total?.count ?? 0) + 1,
        expires_at: now + TTL,
      });
      await tx.put(key, {
        fingerprint,
        state: "pending",
        expires_at: now + TTL,
      });
      return {};
    });
    if (reservation.limited)
      return error(
        429,
        "SUPPORT_LIMITED",
        "送信が集中しています。時間をおいてお試しください。",
      );
    if (reservation.existing) {
      if (reservation.existing.fingerprint !== fingerprint)
        return error(
          409,
          "SUPPORT_CONFLICT",
          "同じ送信IDで別の内容は送れません。",
        );
      if (reservation.existing.state === "sent")
        return reply(201, reservation.existing.receipt);
      return error(
        409,
        "SUPPORT_PENDING",
        "送信結果を確認中です。Issue一覧を確認してください。",
      );
    }
    await this.ctx.storage.setAlarm(now + 86400000);
    try {
      const response = await fetch(
        `https://api.github.com/repos/${this.env.GITHUB_REPOSITORY}/issues`,
        {
          method: "POST",
          redirect: "manual",
          signal: AbortSignal.timeout(12000),
          headers: {
            Authorization: `Bearer ${this.env.GITHUB_TOKEN.trim()}`,
            Accept: "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "Lumvia-Support",
            "X-GitHub-Api-Version": "2022-11-28",
          },
          body: JSON.stringify({ title: data.subject, body: data.body }),
        },
      );
      if ([401, 403, 404].includes(response.status)) {
        await response.body?.cancel();
        await this.ctx.storage.put(key, {
          fingerprint,
          state: "rejected",
          expires_at: now + TTL,
        });
        return error(
          503,
          "GITHUB_ACCESS_DENIED",
          "GitHubの投稿権限を確認してください。",
        );
      }
      const result = await response.json();
      if (
        response.status === 201 &&
        Number.isSafeInteger(result.number) &&
        result.number > 0 &&
        result.html_url ===
          `https://github.com/${this.env.GITHUB_REPOSITORY}/issues/${result.number}`
      ) {
        const receipt = {
          issue_url: result.html_url,
          issue_number: result.number,
        };
        await this.ctx.storage.put(key, {
          fingerprint,
          state: "sent",
          receipt,
          expires_at: now + TTL,
        });
        return reply(201, receipt);
      }
    } catch {
      /* Do not log messages, tokens, IPs, or upstream responses. */
    }
    await this.ctx.storage.put(key, {
      fingerprint,
      state: "uncertain",
      expires_at: now + TTL,
    });
    return error(
      502,
      "SUPPORT_UNCERTAIN",
      "送信結果を確認できませんでした。再送前にIssue一覧を確認してください。",
    );
  }
  async alarm() {
    const entries = await this.ctx.storage.list(),
      now = Date.now();
    const expired = [...entries]
      .filter(([, v]) => v.expires_at <= now)
      .map(([key]) => key);
    if (expired.length) await this.ctx.storage.delete(expired);
    if (entries.size > expired.length)
      await this.ctx.storage.setAlarm(now + 86400000);
  }
}
