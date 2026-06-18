import { useMutation } from "@tanstack/react-query";
import { optimize } from "../lib/api";
import type { TripRequest } from "../lib/schemas";

export function useOptimize() {
  return useMutation({ mutationFn: (req: TripRequest) => optimize(req) });
}
