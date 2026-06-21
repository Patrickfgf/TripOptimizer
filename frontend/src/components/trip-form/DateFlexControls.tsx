import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Props = {
  startDate: string;
  flexDays: number;
  onStartDate: (d: string) => void;
  onFlexDays: (n: number) => void;
};

export function DateFlexControls({ startDate, flexDays, onStartDate, onFlexDays }: Props) {
  return (
    <div className="flex flex-wrap items-end gap-4">
      <div className="flex flex-col gap-1">
        <Label htmlFor="start-date">Start date</Label>
        <Input id="start-date" type="date" value={startDate} onChange={(e) => onStartDate(e.target.value)} />
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="flex">
          Flex window <span className="tabular text-accent">&plusmn;{flexDays}</span>
        </Label>
        <input
          id="flex"
          type="range"
          min={0}
          max={7}
          value={flexDays}
          onChange={(e) => onFlexDays(Number(e.target.value))}
          aria-label="flex days"
        />
      </div>
    </div>
  );
}
