import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Props = {
  startDate: string;
  flexDays: number;
  onStartDate: (d: string) => void;
  onFlexDays: (n: number) => void;
};

const eyebrow = "text-xs font-semibold uppercase tracking-widest text-muted";

export function DateFlexControls({ startDate, flexDays, onStartDate, onFlexDays }: Props) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="start-date" className={eyebrow}>
          Start date
        </Label>
        <Input
          id="start-date"
          type="date"
          value={startDate}
          onChange={(e) => onStartDate(e.target.value)}
          className="w-full sm:w-auto"
        />
      </div>
      <div className="flex flex-col gap-1.5 sm:min-w-[12rem] sm:flex-1">
        <Label htmlFor="flex" className={`flex items-center justify-between ${eyebrow}`}>
          <span>Flex window</span>
          <span className="tabular text-sm font-bold text-teal">±{flexDays}</span>
        </Label>
        <input
          id="flex"
          type="range"
          min={0}
          max={7}
          value={flexDays}
          onChange={(e) => onFlexDays(Number(e.target.value))}
          aria-label="flex days"
          className="w-full"
        />
      </div>
    </div>
  );
}
