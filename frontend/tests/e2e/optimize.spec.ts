import { test, expect } from "@playwright/test";

test("optimizes a 2-city trip end to end", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("combobox", { name: /^origin$/i }).click();
  await page.getByText(/Lisbon/i).first().click();
  await page.getByRole("combobox", { name: /^return$/i }).click();
  await page.getByText(/Berlin/i).first().click();
  await page.getByRole("combobox", { name: /add a city/i }).click();
  await page.getByText(/Barcelona/i).first().click();
  await page.getByLabel(/start date/i).fill("2026-07-01");
  await page.getByRole("button", { name: /optimize route/i }).click();

  await expect(page.getByText(/Cheapest total/i)).toBeVisible();
  await expect(page.getByText(/€\d+/).first()).toBeVisible();
  await expect(page).toHaveURL(/cities=/);
});
