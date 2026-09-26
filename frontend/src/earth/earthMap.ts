import 'maplibre-gl/dist/maplibre-gl.css';

import type { Feature, FeatureCollection } from 'geojson';
import * as maplibregl from 'maplibre-gl';
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

import type { EarthCompany } from '../api/types';
import { cssColor } from '../utilities/cssColor';
import type { MotionLevel } from '../utilities/motionController';

const IMAGERY_TILES = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
const LABEL_TILES = 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}';
const ATTRIBUTION = 'Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community';
const INDIA_CENTRE: [number, number] = [78.9, 21.5];
const SPIN_DEGREES_PER_SECOND = 3;
const SPIN_BELOW_ZOOM = 3.5;

maplibregl.setWorkerUrl(maplibreWorkerUrl);

/** What the map tells its page. */
export interface EarthMapListener {
  onOpen: (company: EarthCompany) => void;
}

/** A satellite globe drawn with MapLibre, with a dot at each company's headquarters, clustered when zoomed out. */
export class EarthMap {
  private readonly map: maplibregl.Map;
  private readonly level: MotionLevel;
  private readonly listener: EarthMapListener | null;
  private readonly companiesById = new Map<string, EarthCompany>();
  private popup: maplibregl.Popup | null = null;
  private spinning: boolean;
  private spinFrame = 0;
  private lastSpinTime = 0;
  private loaded = false;
  private pending: EarthCompany[] | null = null;

  /**
   * Creates the globe in a container.
   * @param container The element to draw in.
   * @param level The animation intensity: maximal turns the globe slowly until it is touched.
   * @param listener Told when a company's popup button is pressed, or null for a map without popups.
   * @param start Where to start: a centre and zoom, or null for India seen from space.
   * @param start.center The centre as [longitude, latitude].
   * @param start.zoom The zoom.
   */
  constructor(container: HTMLElement, level: MotionLevel, listener: EarthMapListener | null, start: { center: [number, number]; zoom: number } | null) {
    this.level = level;
    this.listener = listener;
    this.spinning = level === 'maximal' && start === null;
    this.map = new maplibregl.Map({
      container,
      center: start?.center ?? INDIA_CENTRE,
      zoom: start?.zoom ?? 2.1,
      attributionControl: {
        compact: true,
      },
      style: {
        version: 8,
        projection: {
          type: 'globe',
        },
        sky: {
          'sky-color': '#0b1020',
          'horizon-color': '#30405c',
          'fog-color': '#1e2129',
          'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 1, 5, 1, 8, 0],
        },
        sources: {
          imagery: {
            type: 'raster',
            tiles: [IMAGERY_TILES],
            tileSize: 256,
            maxzoom: 19,
            attribution: ATTRIBUTION,
          },
          labels: {
            type: 'raster',
            tiles: [LABEL_TILES],
            tileSize: 256,
            maxzoom: 19,
          },
        },
        layers: [
          {
            id: 'space',
            type: 'background',
            paint: {
              'background-color': '#05070d',
            },
          },
          {
            id: 'imagery',
            type: 'raster',
            source: 'imagery',
          },
          {
            id: 'labels',
            type: 'raster',
            source: 'labels',
            paint: {
              'raster-opacity': 0.85,
            },
          },
        ],
      },
    });
    this.map.addControl(new maplibregl.NavigationControl(), 'top-right');
    this.map.on('load', this.handleLoad);
    for (const event of ['mousedown', 'touchstart', 'wheel', 'dragstart'] as const) {
      this.map.on(event, this.stopSpinning);
    }
    if (this.spinning) {
      this.spinFrame = requestAnimationFrame(this.spin);
    }
  }

  /**
   * Replaces the companies shown as dots.
   * @param companies The companies with their coordinates.
   */
  setCompanies(companies: EarthCompany[]): void {
    this.companiesById.clear();
    for (const company of companies) {
      this.companiesById.set(company.company_key, company);
    }
    if (!this.loaded) {
      this.pending = companies;
      return;
    }
    const source = this.map.getSource('companies') as maplibregl.GeoJSONSource | undefined;
    source?.setData(this.featureCollection(companies));
  }

  /**
   * Flies to a company and opens its popup.
   * @param company The company.
   */
  focus(company: EarthCompany): void {
    this.stopSpinning();
    const target = {
      center: [company.longitude, company.latitude] as [number, number],
      zoom: company.precision === 'postcode' ? 14 : 11,
    };
    if (this.level === 'off') {
      this.map.jumpTo(target);
    } else {
      this.map.flyTo({
        ...target,
        speed: 1.4,
        curve: 1.6,
      });
    }
    this.showPopup(company);
  }

  /** Stops the animation and frees the map. */
  dispose(): void {
    cancelAnimationFrame(this.spinFrame);
    this.popup?.remove();
    this.map.remove();
  }

  /** Resizes the map to its container, after the page layout changes. */
  resize(): void {
    this.map.resize();
  }

  /** Adds the companies' source and its layers once the style has loaded. */
  private readonly handleLoad = (): void => {
    this.loaded = true;
    const accent = cssColor.read('--accent', '#ff8a65');
    this.map.addSource('companies', {
      type: 'geojson',
      data: this.featureCollection(this.pending ?? []),
      cluster: true,
      clusterRadius: 36,
      clusterMaxZoom: 10,
    });
    this.pending = null;
    this.map.addLayer({
      id: 'company-clusters',
      type: 'circle',
      source: 'companies',
      filter: ['has', 'point_count'],
      paint: {
        'circle-color': accent,
        'circle-opacity': 0.75,
        'circle-radius': ['interpolate', ['linear'], ['get', 'point_count'], 2, 9, 50, 16, 300, 26],
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 1.5,
      },
    });
    this.map.addLayer({
      id: 'company-dots',
      type: 'circle',
      source: 'companies',
      filter: ['!', ['has', 'point_count']],
      paint: {
        'circle-color': accent,
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 2, 4, 12, 8],
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 2,
      },
    });
    this.map.on('click', 'company-clusters', this.handleClusterClick);
    this.map.on('click', 'company-dots', this.handleDotClick);
    for (const layer of ['company-clusters', 'company-dots']) {
      this.map.on('mouseenter', layer, () => {
        this.map.getCanvas().style.cursor = 'pointer';
      });
      this.map.on('mouseleave', layer, () => {
        this.map.getCanvas().style.cursor = '';
      });
    }
  };

  /**
   * Zooms into a cluster until its companies separate.
   * @param event The click on the cluster layer.
   */
  private readonly handleClusterClick = (event: maplibregl.MapLayerMouseEvent): void => {
    const feature = event.features?.[0];
    if (feature === undefined || feature.geometry.type !== 'Point') {
      return;
    }
    const center = feature.geometry.coordinates as [number, number];
    const source = this.map.getSource('companies') as maplibregl.GeoJSONSource;
    const clusterId = feature.properties.cluster_id as number;
    void source.getClusterExpansionZoom(clusterId).then((zoom) => {
      this.map.easeTo({
        center,
        zoom: zoom + 0.5,
        duration: this.level === 'off' ? 0 : 900,
      });
    });
  };

  /**
   * Opens the popup of the company whose dot was clicked.
   * @param event The click on the dots layer.
   */
  private readonly handleDotClick = (event: maplibregl.MapLayerMouseEvent): void => {
    const feature = event.features?.[0];
    if (feature === undefined) {
      return;
    }
    const company = this.companiesById.get(String(feature.properties.company_key));
    if (company !== undefined) {
      this.showPopup(company);
    }
  };

  /**
   * Shows a company's name, address and an open button beside its dot.
   * @param company The company.
   */
  private showPopup(company: EarthCompany): void {
    this.popup?.remove();
    const body = document.createElement('div');
    body.className = 'earth-popup';
    const title = document.createElement('strong');
    title.textContent = company.name;
    body.appendChild(title);
    const facts = document.createElement('div');
    facts.className = 'earth-popup-facts';
    facts.textContent = [company.symbol, company.sector, company.city].filter((part) => part).join(' · ');
    body.appendChild(facts);
    if (company.address !== '') {
      const address = document.createElement('div');
      address.className = 'earth-popup-address';
      address.textContent = company.address;
      body.appendChild(address);
    }
    if (company.precision === 'city') {
      const note = document.createElement('div');
      note.className = 'earth-popup-address';
      note.textContent = 'Placed at the city centre; the postcode was not found.';
      body.appendChild(note);
    }
    if (this.listener !== null && company.instrument_id !== null) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'button button-primary';
      button.textContent = 'Open company';
      button.addEventListener('click', () => this.listener?.onOpen(company));
      body.appendChild(button);
    }
    this.popup = new maplibregl.Popup({
      offset: 12,
      maxWidth: '300px',
    })
      .setLngLat([company.longitude, company.latitude])
      .setDOMContent(body)
      .addTo(this.map);
  }

  /**
   * Turns the companies into GeoJSON points.
   * @param companies The companies.
   * @returns A feature collection with each company's key.
   */
  private featureCollection(companies: EarthCompany[]): FeatureCollection {
    const features: Feature[] = [];
    for (const company of companies) {
      features.push({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [company.longitude, company.latitude],
        },
        properties: {
          company_key: company.company_key,
        },
      });
    }
    return {
      type: 'FeatureCollection',
      features,
    };
  }

  /**
   * Turns the globe slowly while nobody is touching it.
   * @param time The browser's frame timestamp, in milliseconds.
   */
  private readonly spin = (time: number): void => {
    if (!this.spinning) {
      return;
    }
    if (this.lastSpinTime > 0 && this.map.getZoom() < SPIN_BELOW_ZOOM && document.visibilityState === 'visible') {
      const seconds = Math.min((time - this.lastSpinTime) / 1000, 0.1);
      const center = this.map.getCenter();
      this.map.setCenter([center.lng + SPIN_DEGREES_PER_SECOND * seconds, center.lat]);
    }
    this.lastSpinTime = time;
    this.spinFrame = requestAnimationFrame(this.spin);
  };

  /** Stops the slow turn once the user takes control. */
  private readonly stopSpinning = (): void => {
    this.spinning = false;
    cancelAnimationFrame(this.spinFrame);
  };
}
