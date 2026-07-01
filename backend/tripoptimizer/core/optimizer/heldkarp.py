"""Held-Karp DP over (visited_set, last_city). Exact because leg dates depend
only on the set of already-visited cities (fixed days), not their order.

A missing edge (no real fare) is simply never relaxed, so an ordering that can only be
built through a missing leg is never selected. If no fully-real tour exists for an
offset, ``_best_for_offset`` returns None; if none exists for any offset,
``search_heldkarp`` returns None and the runner reports an IncompleteTrip.
"""

from collections.abc import Callable
from datetime import date, timedelta

from tripoptimizer.core.optimizer.models import Itinerary, Leg, TripRequest, TripResult
from tripoptimizer.core.optimizer.schedule import build_legs_dates

FareLookup = Callable[[str, str, date], tuple[float, str] | None]


def _best_for_offset(
    request: TripRequest, fare_lookup: FareLookup, offset: int
) -> Itinerary | None:
    cities = list(request.cities)
    n = len(cities)
    start = request.start_date + timedelta(days=offset)
    days = [request.days_per_city[c] for c in cities]
    full = (1 << n) - 1

    # dp[mask][last] = (cost to be AT `last` having visited exactly `mask`, prev_last)
    dp: list[list[tuple[float, int] | None]] = [[None] * n for _ in range(1 << n)]
    for i, city in enumerate(cities):
        first = fare_lookup(request.origin_airport, city, start)
        if first is not None:  # origin -> city unreachable -> leave that start state unset
            dp[1 << i][i] = (first[0], -1)

    for mask in range(1 << n):
        days_spent = sum(days[i] for i in range(n) if mask & (1 << i))
        fly_date = start + timedelta(days=days_spent)
        for last in range(n):
            state = dp[mask][last]
            if state is None:
                continue
            cost = state[0]
            for nxt in range(n):
                if mask & (1 << nxt):
                    continue
                edge = fare_lookup(cities[last], cities[nxt], fly_date)
                if edge is None:
                    continue  # missing leg: don't relax through it
                ncost = cost + edge[0]
                nmask = mask | (1 << nxt)
                current = dp[nmask][nxt]
                if current is None or ncost < current[0]:
                    dp[nmask][nxt] = (ncost, last)

    return_date = start + timedelta(days=sum(days))
    best_total: float | None = None
    best_last = -1
    for last in range(n):
        state = dp[full][last]
        if state is None:
            continue
        final = fare_lookup(cities[last], request.return_airport, return_date)
        if final is None:
            continue  # last city -> return unreachable
        total = state[0] + final[0]
        if best_total is None or total < best_total:
            best_total, best_last = total, last

    if best_last == -1:
        return None  # no fully-real tour for this offset

    # reconstruct the order from parent pointers
    order_rev: list[str] = []
    mask, last = full, best_last
    while last != -1:
        order_rev.append(cities[last])
        state = dp[mask][last]
        assert state is not None, "DP back-pointer reached an unvisited state"
        prev = state[1]
        mask ^= 1 << last
        last = prev
    order = tuple(reversed(order_rev))

    legs_list: list[Leg] = []
    for o, d, dt_ in build_legs_dates(order, request, offset):
        fare = fare_lookup(o, d, dt_)
        assert fare is not None, "reconstructed leg must be priced (path was feasible)"
        price, source = fare
        legs_list.append(Leg(o, d, dt_, price, source))
    legs = tuple(legs_list)
    return Itinerary(order, offset, legs, sum(leg.price for leg in legs))


def search_heldkarp(request: TripRequest, fare_lookup: FareLookup) -> TripResult | None:
    """Exact cheapest fully-real itinerary via Held-Karp DP, or None if none is fully
    priceable across all offsets. ``alternatives`` is always empty (unlike bruteforce)."""
    best: Itinerary | None = None
    for offset in range(-request.flex_days, request.flex_days + 1):
        candidate = _best_for_offset(request, fare_lookup, offset)
        if candidate is not None and (best is None or candidate.total < best.total):
            best = candidate
    if best is None:
        return None
    return TripResult(best=best, alternatives=())
