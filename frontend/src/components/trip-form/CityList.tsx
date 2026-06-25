import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import type { CityInput } from "../../lib/urlState";

type Props = { cities: CityInput[]; onChange: (cities: CityInput[]) => void };

export function CityList({ cities, onChange }: Props) {
  const setDays = (iata: string, days: number) =>
    onChange(cities.map((c) => (c.iata === iata ? { ...c, days } : c)));
  const remove = (iata: string) => onChange(cities.filter((c) => c.iata !== iata));

  return (
    <ul className="flex flex-col gap-2">
      {cities.map((c, i) => (
        <li
          key={c.iata}
          className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-bento-sm border border-line bg-surface-2 px-3 py-2"
        >
          <span className="tabular w-5 shrink-0 text-center text-sm text-muted">{i + 1}</span>
          <span className="font-semibold tracking-wide">{c.iata}</span>
          <div className="ml-auto flex items-center gap-2">
            <Input
              type="number"
              min={1}
              aria-label={`days for ${c.iata}`}
              className="tabular w-16"
              value={c.days}
              onChange={(e) => setDays(c.iata, Number(e.target.value))}
            />
            <span className="text-sm text-muted">days</span>
            <Button
              variant="ghost"
              size="sm"
              aria-label={`remove ${c.iata}`}
              onClick={() => remove(c.iata)}
            >
              &times;
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}
