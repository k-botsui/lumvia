import { expect, test } from "@playwright/test";

test("add → save Cell → organize → search → reopen range", async ({
  page,
  context,
}) => {
  test.skip(
    !process.env.LUMVIA_E2E_EMAIL || !process.env.LUMVIA_E2E_PASSWORD,
    "Use an explicitly configured disposable local test account.",
  );
  const suffix = Date.now().toString();
  const cellName = `E2E moment ${suffix}`;
  const shelfName = `E2E Shelf ${suffix}`;
  let mediaId: string | null = null;
  let shelfId: string | null = null;
  try {
    await page.goto("/");
    await page.getByLabel("メールアドレス").fill(process.env.LUMVIA_E2E_EMAIL!);
    await page
      .getByLabel("パスワード", { exact: true })
      .fill(process.env.LUMVIA_E2E_PASSWORD!);
    await page.getByRole("button", { name: "ログイン", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "追加する", exact: true }),
    ).toBeVisible();
    // A local library must not pause requests when WebKit reports no Internet.
    await page.addInitScript(() =>
      Object.defineProperty(navigator, "onLine", { get: () => false }),
    );
    await page.reload();
    await page.getByRole("button", { name: "追加する", exact: true }).click();
    await page
      .getByRole("tab", { name: "ファイルを追加", exact: true })
      .click();
    await page
      .getByRole("button", { name: "サンプル動画で試す", exact: true })
      .click();
    await expect(
      page.getByText("追加しました。再生の準備をしています。", { exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: /^ライブラリ \d/ }).click();
    await page
      .getByRole("button", {
        name: "Lumvia サンプル — 3つのシーンを開く",
        exact: true,
      })
      .first()
      .click({ button: "right" });
    await expect(
      page.getByRole("menuitem", { name: "Shelfに追加", exact: true }),
    ).toBeVisible();
    await page.getByRole("menu").press("Escape");
    await page
      .getByRole("button", {
        name: "Lumvia サンプル — 3つのシーンを開く",
        exact: true,
      })
      .first()
      .click();
    await expect(
      page.getByRole("button", { name: "Cellを作成", exact: true }),
    ).toBeEnabled({ timeout: 30000 });
    mediaId = new URL(page.url()).searchParams.get("media");
    await page
      .getByRole("button", { name: "動画から選ぶ", exact: true })
      .click();
    const coverDialog = page.getByRole("dialog", {
      name: "動画からカバーを選ぶ",
      exact: true,
    });
    await expect(
      coverDialog.getByRole("button", { name: "この場面をカバーにする" }),
    ).toBeEnabled();
    await coverDialog
      .getByRole("slider", { name: "カバーに使う場面" })
      .press("End");
    await expect(
      coverDialog.getByRole("button", { name: "この場面をカバーにする" }),
    ).toBeEnabled();
    const coverResponse = page.waitForResponse(
      (response) =>
        response.url().includes(`/media/${mediaId}/frame-cover`) &&
        response.request().method() === "POST",
    );
    await coverDialog
      .getByRole("button", { name: "この場面をカバーにする" })
      .click();
    expect((await coverResponse).status()).toBe(200);
    await expect(coverDialog).not.toBeVisible();
    await page.getByRole("button", { name: "Cellを作成", exact: true }).click();
    await page.getByLabel("タイトル", { exact: true }).fill(cellName);
    await page.getByText("時刻を細かく指定", { exact: true }).click();
    await page.getByLabel("開始（秒）").fill("1.25");
    await page.getByLabel("終了（秒）").fill("2.75");
    await page.getByRole("button", { name: "Cellを保存", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: cellName, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("slider", { name: "Cellの再生位置" }),
    ).toHaveAttribute("max", "1.5");
    await expect(page.locator("video")).not.toHaveAttribute("controls", "");
    await page.getByRole("button", { name: "閉じる", exact: true }).click();
    await page.getByRole("button", { name: "Shelf", exact: true }).click();
    await page
      .getByRole("button", { name: "Shelfを作成", exact: true })
      .click();
    await page
      .getByRole("textbox", { name: "名前", exact: true })
      .fill(shelfName);
    await page.getByRole("button", { name: "保存する", exact: true }).click();
    await page
      .getByRole("button", {
        name: new RegExp(shelfName + ".*動画.*Cells"),
      })
      .click();
    shelfId = new URL(page.url()).searchParams.get("shelf");
    await page
      .getByRole("textbox", { name: "ライブラリを検索", exact: true })
      .fill(cellName);
    await page
      .getByRole("textbox", { name: "ライブラリを検索", exact: true })
      .press("Enter");
    await page
      .getByRole("button", { name: cellName + "を整理", exact: true })
      .click();
    await page.getByRole("checkbox", { name: shelfName, exact: true }).click();
    await expect(
      page.getByRole("checkbox", { name: shelfName, exact: true }),
    ).toBeChecked();
    await page.getByRole("button", { name: "完了", exact: true }).click();
    await page
      .getByRole("button", { name: cellName + "を開く", exact: true })
      .click();
    await expect
      .poll(() =>
        page.locator("video").evaluate((v: HTMLVideoElement) => v.currentTime),
      )
      .toBeCloseTo(1.25, 1);
    await page.getByRole("button", { name: "Cellを再生", exact: true }).click();
    await expect
      .poll(() =>
        page.locator("video").evaluate((v: HTMLVideoElement) => v.currentTime),
      )
      .toBeCloseTo(2.75, 1);
    await expect
      .poll(() =>
        page.locator("video").evaluate((v: HTMLVideoElement) => v.paused),
      )
      .toBe(true);
    await page.getByRole("button", { name: "Cellを再生", exact: true }).click();
    await expect
      .poll(() =>
        page.locator("video").evaluate((v: HTMLVideoElement) => v.currentTime),
      )
      .toBeLessThan(2.75);
    await page.getByRole("slider", { name: "Cellの再生位置" }).press("End");
    await expect
      .poll(() =>
        page.locator("video").evaluate((v: HTMLVideoElement) => v.paused),
      )
      .toBe(true);
    await expect
      .poll(() =>
        page.locator("video").evaluate((v: HTMLVideoElement) => v.currentTime),
      )
      .toBeCloseTo(2.75, 1);
    await page.getByRole("slider", { name: "Cellの再生位置" }).press("Home");
    await expect
      .poll(() =>
        page.locator("video").evaluate((v: HTMLVideoElement) => v.currentTime),
      )
      .toBeCloseTo(1.25, 1);
  } finally {
    const cookies = await context.cookies();
    const csrf = cookies.find((c) => c.name === "lumvia_csrf")?.value;
    if (csrf) {
      const headers = {
        "X-CSRF-Token": csrf,
        Origin: process.env.LUMVIA_E2E_URL || "http://127.0.0.1:3000",
      };
      if (mediaId)
        await context.request.delete(`/api/v1/media/${mediaId}`, { headers });
      if (shelfId)
        await context.request.delete(`/api/v1/shelves/${shelfId}`, {
          headers,
        });
    }
  }
});
