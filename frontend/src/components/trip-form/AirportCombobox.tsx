import { useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Button } from "@/components/ui/button";
import type { Airport } from "../../lib/schemas";

type Props = {
  airports: Airport[];
  value: string | null;
  onChange: (iata: string) => void;
  label: string;
};

export function AirportCombobox({ airports, value, onChange, label }: Props) {
  const [open, setOpen] = useState(false);
  const selected = airports.find((a) => a.iata === value);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" role="combobox" aria-label={label} className="w-full justify-between">
          {selected ? `${selected.city} (${selected.iata})` : label}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="p-0">
        <Command>
          <CommandInput placeholder={`Search ${label.toLowerCase()}...`} />
          <CommandList>
            <CommandEmpty>No airport found.</CommandEmpty>
            <CommandGroup>
              {airports.map((a) => (
                <CommandItem
                  key={a.iata}
                  value={`${a.city} ${a.name} ${a.iata}`}
                  onSelect={() => {
                    onChange(a.iata);
                    setOpen(false);
                  }}
                >
                  {a.city} ({a.iata}) &mdash; {a.country}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
