import { useQuery } from "@tanstack/react-query";
import { getAirports } from "../lib/api";

export function useAirports() {
  return useQuery({ queryKey: ["airports"], queryFn: getAirports, staleTime: Infinity });
}
