import { Plane } from "lucide-react";
import { useAirports } from "../../hooks/useAirports";
import { AirportCombobox } from "./AirportCombobox";
import { CityList } from "./CityList";
import { DateFlexControls } from "./DateFlexControls";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { TripRequestSchema } from "../../lib/schemas";
import { toApiRequest, type TripInput } from "../../lib/urlState";

type Props = {
  value: TripInput;
  onChange: (trip: TripInput) => void;
  onSubmit: (trip: TripInput) => void;
};

const eyebrow = "text-xs font-semibold uppercase tracking-widest text-muted";

export function TripForm({ value, onChange, onSubmit }: Props) {
  const { data: airports = [] } = useAirports();
  const patch = (p: Partial<TripInput>) => onChange({ ...value, ...p });
  const isValid = TripRequestSchema.safeParse(toApiRequest(value)).success;

  const addCity = (iata: string) => {
    if (value.cities.some((c) => c.iata === iata)) return;
    patch({ cities: [...value.cities, { iata, days: 2 }] });
  };

  return (
    <form
      className="flex flex-col gap-5 rounded-bento border border-line bg-surface-2 p-5 shadow-ticket sm:p-6"
      onSubmit={(e) => {
        e.preventDefault();
        if (isValid) onSubmit(value);
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <Label className={eyebrow}>Origin</Label>
          <AirportCombobox
            airports={airports}
            value={value.origin_airport}
            onChange={(i) => patch({ origin_airport: i })}
            label="Origin"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label className={eyebrow}>Return</Label>
          <AirportCombobox
            airports={airports}
            value={value.return_airport}
            onChange={(i) => patch({ return_airport: i })}
            label="Return"
          />
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <Label className={eyebrow}>
          Destinations{" "}
          <span className="font-normal normal-case tracking-normal text-muted/80">
            — in any order, we reorder for the cheapest
          </span>
        </Label>
        <CityList cities={value.cities} onChange={(c) => patch({ cities: c })} />
        <AirportCombobox airports={airports} value={null} onChange={addCity} label="Add a city" />
      </div>

      <DateFlexControls
        startDate={value.start_date}
        flexDays={value.flex_days}
        onStartDate={(d) => patch({ start_date: d })}
        onFlexDays={(n) => patch({ flex_days: n })}
      />

      <Button type="submit" disabled={!isValid} className="h-11 bg-accent text-surface hover:bg-accent/90">
        <Plane className="h-4 w-4 -rotate-45" aria-hidden /> Optimize route
      </Button>
    </form>
  );
}
