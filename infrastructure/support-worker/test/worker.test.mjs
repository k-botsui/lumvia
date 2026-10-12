import test from "node:test";
import assert from "node:assert/strict";
import worker, { SupportInbox, parseMessage } from "../src/worker.mjs";

class Storage {
  values = new Map();
  queue = Promise.resolve();
  async get(k) {
    return structuredClone(this.values.get(k));
  }
  async put(k, v) {
    this.values.set(k, structuredClone(v));
  }
  async delete(keys) {
    for (const k of Array.isArray(keys) ? keys : [keys]) this.values.delete(k);
  }
  async list() {
    return new Map(this.values);
  }
  async setAlarm() {}
  async transaction(action) {
    const run = this.queue.then(() => action(this));
    this.queue = run.catch(() => {});
    return run;
  }
}
const payload = () => ({
  request_id: crypto.randomUUID(),
  subject: "使い方について",
  body: "動画の操作について質問します。",
});
const request = (data, ip = "203.0.113.9") =>
  new Request("https://inbox/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-client-ip": ip },
    body: JSON.stringify(data),
  });
function setup() {
  const storage = new Storage();
  const env = {
    GITHUB_REPOSITORY: "example/lumvia",
    GITHUB_TOKEN: "test-credential-not-a-real-token",
  };
  return { storage, env, inbox: new SupportInbox({ storage }, env) };
}

test("anonymous submit sends only typed title and body; retries are idempotent", async () => {
  const { storage, inbox } = setup();
  let writes = 0;
  const previous = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    writes++;
    assert.equal(url, "https://api.github.com/repos/example/lumvia/issues");
    assert.deepEqual(JSON.parse(options.body), {
      title: "使い方について",
      body: "動画の操作について質問します。",
    });
    return Response.json(
      { number: 7, html_url: "https://github.com/example/lumvia/issues/7" },
      { status: 201 },
    );
  };
  try {
    const data = payload();
    const responses = await Promise.all([
      inbox.fetch(request(data)),
      inbox.fetch(request(data)),
    ]);
    assert.equal(writes, 1);
    assert.ok(responses.some((r) => r.status === 201));
    assert.equal((await inbox.fetch(request(data))).status, 201);
    assert.equal(
      (await inbox.fetch(request({ ...data, body: "changed" }))).status,
      409,
    );
    const persisted = JSON.stringify([...storage.values]);
    assert.ok(
      !persisted.includes(data.subject) &&
        !persisted.includes(data.body) &&
        !persisted.includes("203.0.113.9"),
    );
  } finally {
    globalThis.fetch = previous;
  }
});
test("timeout is not automatically retried against GitHub", async () => {
  const { inbox } = setup();
  let writes = 0;
  const previous = globalThis.fetch;
  globalThis.fetch = async () => {
    writes++;
    throw new Error("network");
  };
  try {
    const data = payload();
    assert.equal((await inbox.fetch(request(data))).status, 502);
    assert.equal((await inbox.fetch(request(data))).status, 409);
    assert.equal(writes, 1);
  } finally {
    globalThis.fetch = previous;
  }
});
test("per-IP limit is enforced before the fourth GitHub write", async () => {
  const { inbox } = setup();
  let writes = 0;
  const previous = globalThis.fetch;
  globalThis.fetch = async () => {
    writes++;
    return Response.json(
      {
        number: writes,
        html_url: `https://github.com/example/lumvia/issues/${writes}`,
      },
      { status: 201 },
    );
  };
  try {
    for (let i = 0; i < 3; i++)
      assert.equal((await inbox.fetch(request(payload()))).status, 201);
    assert.equal((await inbox.fetch(request(payload()))).status, 429);
    assert.equal(writes, 3);
  } finally {
    globalThis.fetch = previous;
  }
});
test("global quota prevents writes even from a new IP", async () => {
  const { storage, inbox } = setup();
  const day = new Date().toISOString().slice(0, 10);
  await storage.put(`daily:${day}`, {
    count: 50,
    expires_at: Date.now() + 1000,
  });
  assert.equal(
    (await inbox.fetch(request(payload(), "198.51.100.1"))).status,
    429,
  );
});
test("extra fields, arbitrary repository and invalid input are rejected", () => {
  assert.equal(parseMessage({ ...payload(), repository: "other/repo" }), null);
  assert.equal(parseMessage({ ...payload(), body: " " }), null);
  assert.equal(parseMessage({ ...payload(), subject: "a\nb" }), null);
  assert.equal(parseMessage({ ...payload(), body: "x".repeat(10001) }), null);
});
test("public endpoint returns status without login and rejects oversize bodies", async () => {
  const { env } = setup();
  assert.equal(
    (await worker.fetch(new Request("https://worker/status"), env)).status,
    200,
  );
  const req = new Request("https://worker/issues", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "x".repeat(45001),
  });
  assert.equal((await worker.fetch(req, env)).status, 422);
  assert.equal(
    (await worker.fetch(new Request("https://worker/other"), env)).status,
    404,
  );
});
test("alarm expires receipts and counters", async () => {
  const { storage, inbox } = setup();
  await storage.put("old", { expires_at: 0 });
  await storage.put("new", { expires_at: Date.now() + 10000 });
  await inbox.alarm();
  assert.equal(await storage.get("old"), undefined);
  assert.ok(await storage.get("new"));
});
