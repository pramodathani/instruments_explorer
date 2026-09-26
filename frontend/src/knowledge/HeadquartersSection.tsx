import { useEffect, useRef } from 'react';
import { Link } from 'react-router';

import type { EarthCompany, Headquarters } from '../api/types';
import { useMotionLevel } from '../components/useMotionLevel';
import type { EarthMap } from '../earth/earthMap';

/** Props for HeadquartersSection. */
interface HeadquartersSectionProps {
  headquarters: Headquarters;
  company: EarthCompany | null;
  instrumentId: string;
}

/**
 * The company's headquarters address with a small satellite map centred on it.
 * @param props The address, the company as a map dot when it could be placed, and the instrument for the Earth link.
 * @returns The section.
 */
export function HeadquartersSection(props: HeadquartersSectionProps) {
  const { headquarters, company, instrumentId } = props;
  const level = useMotionLevel();
  const containerReference = useRef<HTMLDivElement>(null);
  const location = headquarters.location;

  useEffect(() => {
    const container = containerReference.current;
    if (container === null || company === null || location === null) {
      return undefined;
    }
    let cancelled = false;
    let map: EarthMap | null = null;
    import('../earth/earthMap')
      .then((module) => {
        if (cancelled) {
          return;
        }
        map = new module.EarthMap(container, level, null, {
          center: [location.longitude, location.latitude],
          zoom: location.precision === 'postcode' ? 13 : 10,
        });
        map.setCompanies([company]);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      map?.dispose();
    };
  }, [company, location, level]);

  const lines = [...headquarters.address_lines, [headquarters.city, headquarters.postcode].filter((part) => part).join(' '), headquarters.state, headquarters.country].filter((part) => part);

  return (
    <section className="headquarters">
      <h3 className="section-heading">Headquarters</h3>
      <div className="headquarters-layout">
        <address className="headquarters-address">
          {lines.map((line) => (
            <div key={line}>{line}</div>
          ))}
          {headquarters.phone ? <div className="muted">Phone {headquarters.phone}</div> : null}
          {location !== null ? (
            <Link to={`/earth?focus=${instrumentId}`} className="headquarters-earth">
              Show on the Earth globe
            </Link>
          ) : null}
          {location !== null && location.precision === 'city' ? <div className="muted">The map shows the city centre; the postcode was not found.</div> : null}
          {!headquarters.geocoder_ready ? <div className="muted">The map appears once the postcode list is downloaded; the Earth page shows how.</div> : null}
        </address>
        {location !== null ? <div className="headquarters-map" ref={containerReference} /> : null}
      </div>
    </section>
  );
}
