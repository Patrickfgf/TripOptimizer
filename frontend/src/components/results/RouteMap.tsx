import { ComposableMap, Geographies, Geography, Line, Marker } from "react-simple-maps";
import geoData from "world-atlas/countries-110m.json";
import type { Airport, Leg } from "../../lib/schemas";

type Props = { legs: Leg[]; airports: Airport[] };

export function RouteMap({ legs, airports }: Props) {
  const byIata = new Map(airports.map((a) => [a.iata, a]));
  const coord = (iata: string): [number, number] | null => {
    const a = byIata.get(iata);
    return a ? [a.lon, a.lat] : null;
  };
  const distinct = Array.from(new Set(legs.flatMap((l) => [l.origin, l.destination])));

  return (
    <div className="overflow-hidden rounded-bento border border-line bg-surface-2">
      <ComposableMap projection="geoAzimuthalEqualArea" projectionConfig={{ rotate: [-10, -52, 0], scale: 700 }}>
        <Geographies geography={geoData as object}>
          {({ geographies }) =>
            geographies.map((geo: { rsmKey: string }) => (
              <Geography key={geo.rsmKey} geography={geo} fill="#efe6d4" stroke="#e7ddc9" />
            ))
          }
        </Geographies>
        {legs.map((leg, i) => {
          const from = coord(leg.origin);
          const to = coord(leg.destination);
          if (!from || !to) return null;
          return <Line key={i} from={from} to={to} stroke="#e08a00" strokeWidth={1.6} />;
        })}
        {distinct.map((iata) => {
          const c = coord(iata);
          if (!c) return null;
          return (
            <Marker key={iata} coordinates={c}>
              <circle r={3} fill="#1a1410" />
            </Marker>
          );
        })}
      </ComposableMap>
    </div>
  );
}
