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
        <li key={c.iata} className="flex items-center gap-3 rounded-bento border border-line bg-surface-2 p-2">
          <span className="tabular w-6 text-muted">{i + 1}.</span>
          <span className="font-medium">{c.iata}</span>
          <Input
            type="number"
            min={1}
            aria-label={`days for ${c.iata}`}
            className="tabular w-20"
            value={c.days}
            onChange={(e) => setDays(c.iata, Number(e.target.value))}
          />
          <span className="text-sm text-muted">days</span>
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto"
            aria-label={`remove ${c.iata}`}
            onClick={() => remove(c.iata)}
          >
            &times;
          </Button>
        </li>
      ))}
    </ul>
  );
}
