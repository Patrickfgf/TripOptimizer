const EUR = new Intl.NumberFormat("en-IE", {
  style: "currency",
  currency: "EUR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * Format a EUR amount with the € symbol and exactly two decimals.
 *
 * Two-decimal fixed output keeps price columns aligned under tabular-nums and
 * tames raw fares / float subtraction (e.g. 50.98984978742 → "€50.99",
 * 251 - 214 → "€37.00"). Adds a thousands separator for larger totals.
 */
export function formatEur(amount: number): string {
  return EUR.format(amount);
}
