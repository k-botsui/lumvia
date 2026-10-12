import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

test("right-click keeps the complete selection and deletion requires confirmation", async ({
  page,
  context,
  baseURL,
}) => {
  test.skip(
    !process.env.LUMVIA_E2E_EMAIL || !process.env.LUMVIA_E2E_PASSWORD,
    "Disposable test account required.",
  );
  const login = await context.request.post("/api/v1/auth/login", {
    headers: { Origin: baseURL! },
    data: {
      email: process.env.LUMVIA_E2E_EMAIL,
      password: process.env.LUMVIA_E2E_PASSWORD,
    },
  });
  expect(login.status()).toBe(200);
  const csrf = (await context.cookies()).find(
    (cookie) => cookie.name === "lumvia_csrf",
  )!.value;
  const headers = { Origin: baseURL!, "X-CSRF-Token": csrf };
  const ids: string[] = [];
  try {
    for (const name of ["context-one.mp4", "context-two.mp4"]) {
      const response = await context.request.post("/api/v1/media", {
        headers,
        multipart: {
          file: {
            name,
            mimeType: "video/mp4",
            buffer: readFileSync("public/sample.mp4"),
          },
        },
      });
      expect(response.status()).toBe(201);
      ids.push((await response.json()).id);
    }
    await page.goto("/?view=library");
    await page.getByRole("button", { name: "選択", exact: true }).click();
    for (const name of ["context-one.mp4", "context-two.mp4"]) {
      await page
        .getByRole("checkbox", {
          name: name.replace(/\.mp4$/, "") + "を選択",
          exact: true,
        })
        .check();
    }
    await page
      .getByRole("button", { name: "context-oneを選択", exact: true })
      .click({ button: "right" });
    await expect(
      page.getByRole("menuitem", { name: "選択した項目をShelfに追加" }),
    ).toBeVisible();
    await page.getByRole("menuitem", { name: "選択した項目を削除…" }).click();
    await expect(
      page.getByRole("dialog", { name: "2件を削除しますか？" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "キャンセル", exact: true }).click();
    for (const id of ids)
      expect((await context.request.get("/api/v1/media/" + id)).status()).toBe(
        200,
      );
  } finally {
    for (const id of ids)
      await context.request.delete("/api/v1/media/" + id, { headers });
  }
});
