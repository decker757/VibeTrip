import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { importLibrary, setOptions } from '@googlemaps/js-api-loader';

const BROWSER_MAPS_KEY = import.meta.env.VITE_GOOGLE_MAPS_BROWSER_KEY;
const MAP_ID = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID || 'DEMO_MAP_ID';

function decodePolyline(encoded = '') {
  const points = [];
  let index = 0;
  let latitude = 0;
  let longitude = 0;
  while (index < encoded.length) {
    let result = 0;
    let shift = 0;
    let byte;
    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    latitude += result & 1 ? ~(result >> 1) : result >> 1;
    result = 0;
    shift = 0;
    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    longitude += result & 1 ? ~(result >> 1) : result >> 1;
    points.push({ lat: latitude / 1e5, lng: longitude / 1e5 });
  }
  return points;
}

function escapeHtml(value = '') {
  return value.replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
}

function infoContent(candidate) {
  const quote = candidate.review_quote ? `<p class="google-review">“${escapeHtml(candidate.review_quote)}”</p><small>${escapeHtml(candidate.review_author || 'Google reviewer')}</small>` : '<small>Reviews available in Google Maps</small>';
  const cost = candidate.cost_label ? `<span>${escapeHtml(candidate.cost_label)}</span>` : '';
  return `<div class="map-info-card"><strong>${escapeHtml(candidate.name)}</strong><span>${escapeHtml(candidate.category || 'Place')} · ${candidate.price_label || '$'}</span><span>★ ${Number(candidate.rating || 0).toFixed(1)} (${Number(candidate.review_count || 0).toLocaleString()}) · ${candidate.detour_minutes || 0} min detour</span>${cost}${quote}<a href="${escapeHtml(candidate.google_maps_uri || '#')}" target="_blank" rel="noreferrer">Open in Google Maps ↗</a></div>`;
}

const GoogleRouteMap = forwardRef(function GoogleRouteMap({ route, candidates, fallback, onSelectCandidate }, ref) {
  const mapElement = useRef(null);
  const mapRef = useRef(null);
  const overlaysRef = useRef([]);
  const routePointsRef = useRef([]);
  const markerRefs = useRef(new Map());
  const infoWindowRef = useRef(null);
  const onSelectCandidateRef = useRef(onSelectCandidate);
  const [state, setState] = useState(BROWSER_MAPS_KEY && route?.polyline ? 'loading' : 'fallback');

  useEffect(() => {
    onSelectCandidateRef.current = onSelectCandidate;
  }, [onSelectCandidate]);

  useImperativeHandle(ref, () => ({
    focusStop(stop) {
      if (!mapRef.current || routePointsRef.current.length === 0) return false;
      const candidate = candidates.find((item) => item.id === stop?.place_id && item.location);
      const points = routePointsRef.current;
      const fallbackIndex = stop?.type === 'stay' ? points.length - 1 : stop?.type === 'coffee' ? Math.round((points.length - 1) * 0.12) : stop?.type === 'fuel' ? Math.round((points.length - 1) * 0.38) : Math.round((points.length - 1) * 0.58);
      const position = candidate?.location ? { lat: candidate.location.latitude, lng: candidate.location.longitude } : points[Math.max(0, Math.min(points.length - 1, fallbackIndex))];
      mapRef.current.panTo(position);
      mapRef.current.setZoom(candidate ? 14 : 11);
      const marker = candidate ? markerRefs.current.get(candidate.id) : null;
      if (marker && infoWindowRef.current) {
        infoWindowRef.current.setContent(infoContent(candidate));
        infoWindowRef.current.open({ map: mapRef.current, anchor: marker });
      }
      return true;
    },
  }), [candidates]);

  useEffect(() => {
    let cancelled = false;
    async function renderMap() {
      if (!BROWSER_MAPS_KEY || !route?.polyline) {
        setState('fallback');
        return;
      }
      // The host is rendered as soon as a route exists. If React has not
      // committed it yet, let the effect run again after that commit rather
      // than permanently falling back to the SVG preview.
      if (!mapElement.current) {
        setState('loading');
        return;
      }
      try {
        setOptions({ key: BROWSER_MAPS_KEY, v: 'weekly' });
        const [{ Map, InfoWindow, TrafficLayer }, { AdvancedMarkerElement, PinElement }] = await Promise.all([
          importLibrary('maps'),
          importLibrary('marker'),
        ]);
        if (cancelled) return;
        const points = decodePolyline(route.polyline);
        routePointsRef.current = points;
        const map = new Map(mapElement.current, { center: points[0], zoom: 8, mapTypeControl: false, streetViewControl: false, fullscreenControl: false, mapId: MAP_ID });
        const bounds = new google.maps.LatLngBounds();
        points.forEach((point) => bounds.extend(point));
        const trafficLayer = new TrafficLayer();
        trafficLayer.setMap(map);
        const routeLine = new google.maps.Polyline({ path: points, geodesic: true, strokeColor: '#1e7bff', strokeOpacity: 0.95, strokeWeight: 5, map });
        const infoWindow = new InfoWindow({ disableAutoPan: false });
        infoWindowRef.current = infoWindow;
        markerRefs.current.clear();
        const overlays = [routeLine, trafficLayer];
        candidates.forEach((candidate) => {
          if (!candidate.location) return;
          const pin = new PinElement({ background: '#78966d', borderColor: '#ffffff', glyphColor: '#ffffff', scale: 1.05 });
          const marker = new AdvancedMarkerElement({ map, position: { lat: candidate.location.latitude, lng: candidate.location.longitude }, title: candidate.name, content: pin, gmpClickable: true });
          markerRefs.current.set(candidate.id, marker);
          const open = () => {
            infoWindow.setContent(infoContent(candidate));
            infoWindow.open({ map, anchor: marker });
          };
          marker.addEventListener('gmp-click', () => {
            open();
            onSelectCandidateRef.current?.(candidate);
          });
          pin.addEventListener('mouseenter', open);
          overlays.push(marker);
        });
        bounds.extend(points[0]);
        map.fitBounds(bounds, 45);
        mapRef.current = map;
        overlaysRef.current = overlays;
        setState('ready');
      } catch (error) {
        console.warn('Google Maps JavaScript API unavailable; using the fallback map.', error);
        setState('error');
      }
    }
    renderMap();
    return () => {
      cancelled = true;
      overlaysRef.current.forEach((overlay) => {
        if (overlay.setMap) overlay.setMap(null);
        if (overlay.element) overlay.element.replaceChildren();
      });
      overlaysRef.current = [];
      mapRef.current = null;
      routePointsRef.current = [];
      markerRefs.current.clear();
      infoWindowRef.current = null;
    };
  }, [route?.polyline, candidates]);

  if (!BROWSER_MAPS_KEY || !route?.polyline || state === 'error') return fallback;
  return <div className="dynamic-map"><div className="google-map-host" ref={mapElement} /><span className="map-provider-badge">Google Maps · live traffic</span></div>;
});

GoogleRouteMap.displayName = 'GoogleRouteMap';

export default GoogleRouteMap;
