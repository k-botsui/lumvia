import { expect, test } from "@playwright/test";

test("shared links → partial success → duplicate → edit → search", async ({
  page,
  context,
}) => {
  test.skip(
    !process.env.LUMVIA_E2E_EMAIL || !process.env.LUMVIA_E2E_PASSWORD,
    "Use a disposable local account.",
  );
  const ids: string[] = [];
  const title = `Saved link ${Date.now()}`;
  try {
    await page.goto("/");
    await page.getByLabel("メールアドレス").fill(process.env.LUMVIA_E2E_EMAIL!);
    await page
      .getByLabel("パスワード", { exact: true })
      .fill(process.env.LUMVIA_E2E_PASSWORD!);
    await page.getByRole("button", { name: "ログイン", exact: true }).click();
    await page.getByRole("button", { name: "追加する", exact: true }).click();
    // A synthetic Instagram ID exercises fallback without depending on a live platform response.
    const url = `https://www.instagram.com/reel/QA_${Date.now()}/`;
    await page
      .getByLabel("動画・投稿の共有リンク")
      .fill(`${url}\nhttps://x.com/home`);
    const createdResponse = page.waitForResponse(
      (r) => r.url().endsWith("/api/v1/imports") && r.status() === 201,
    );
    await page.getByRole("button", { name: "2件を追加", exact: true }).click();
    ids.push((await (await createdResponse).json()).media.id);
    await expect(
      page.getByRole("heading", {
        name: "1件追加 · 0件保存済み · 1件未追加",
        exact: true,
      }),
    ).toBeVisible();
    await expect(page.getByLabel("動画・投稿の共有リンク")).toHaveValue(
      "https://x.com/home",
    );
    await page.getByLabel("動画・投稿の共有リンク").fill(url);
    await page
      .getByRole("button", { name: "ライブラリに追加", exact: true })
      .click();
    await expect(
      page.getByRole("heading", {
        name: "0件追加 · 1件保存済み · 0件未追加",
        exact: true,
      }),
    ).toBeVisible();
    await expect(page.getByLabel("動画・投稿の共有リンク")).toHaveValue("");
    await expect(page.getByLabel("タイトル（任意）")).toHaveValue("");
    await page.getByRole("button", { name: "開く", exact: true }).click();
    await expect(
      page.getByRole("link", { name: "Instagramで開く", exact: true }),
    ).toHaveAttribute("href", url);
    await expect(
      page.getByRole("button", { name: "区間を切り取る", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "タイトル・メモ・タグを編集", exact: true })
      .click();
    await page.getByLabel("タイトル", { exact: true }).fill(title);
    await page.getByLabel("メモ", { exact: true }).fill(title + " note");
    await page.getByLabel("タグ", { exact: true }).fill("参考");
    await page.getByRole("button", { name: "変更を保存", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "閉じる", exact: true }).click();
    await page.getByLabel("ライブラリを検索").fill(title + " note");
    await page.getByLabel("ライブラリを検索").press("Enter");
    await expect(
      page.getByRole("button", { name: title + "を開く", exact: true }),
    ).toBeVisible();
  } finally {
    const csrf = (await context.cookies()).find(
      (c) => c.name === "lumvia_csrf",
    )?.value;
    for (const id of ids)
      await context.request.delete("/api/v1/media/" + id, {
        headers: { "X-CSRF-Token": csrf || "" },
      });
  }
});
