import Icon from './Icon';
import { formatDuration } from '../app/formatters';

export function RouteMap({ candidates = [], from = 'Boston, MA', to = 'New York, NY', routeStats, onFocusCandidate }) {
  const markerPositions = [[30, 22], [43, 37], [55, 53], [67, 68]];
  return (
    <div className="map-canvas" aria-label={`Map preview of the route from ${from} to ${to}`}>
      <div className="map-controls"><button className="map-button active" aria-label="Map view"><Icon name="map" size={16} /></button><button className="map-button" aria-label="Layers"><Icon name="layers" size={16} /></button></div>
      <div className="map-zoom"><button aria-label="Zoom in"><Icon name="plus" size={16} /></button><button aria-label="Zoom out"><span>−</span></button></div>
      <div className="map-label label-boston">{from.split(',')[0].toUpperCase()}</div><div className="map-label label-providence">PROVIDENCE</div><div className="map-label label-newhaven">NEW HAVEN</div><div className="map-label label-nyc">{to.split(',')[0].toUpperCase()}</div>
      {candidates.slice(0, 4).map((candidate, index) => { const [left, top] = markerPositions[index]; return <button className="map-place" key={candidate.id} style={{ left: `${left}%`, top: `${top}%` }} aria-label={`${candidate.name}, ${candidate.enjoyment_score} enjoyment score`} title={`${candidate.name} · ${candidate.detour_minutes} min detour`} onClick={() => onFocusCandidate?.(candidate)}><Icon name="sparkles" size={12} /></button>; })}
      <svg className="route-art" viewBox="0 0 800 500" preserveAspectRatio="none" role="presentation">
        <path className="water-shape" d="M555 0c-11 47-7 82 12 113 17 28 20 56 10 83-11 29-5 63 18 95 26 36 44 66 45 111l160 98V0H555Z" />
        <path className="state-line" d="M286 54c-40 44-59 102-63 157-3 52 26 64 50 94 22 28 22 73 58 91 28 14 80-2 111-27 32-25 54-39 71-80 12-29 13-69-5-107-20-42-20-80-8-128" />
        <path className="state-line thin" d="M125 143c51 12 92 15 132 13M275 311c71 18 126 22 188 9M364 55c23 42 49 60 86 71M147 367c56-15 105-4 145 26" />
        <path className="road-muted" d="M120 92C188 110 267 126 347 164c73 35 103 80 126 151 13 39 23 81 52 110" /><path className="route-line" d="M120 92C188 110 267 126 347 164c73 35 103 80 126 151 13 39 23 81 52 110" /><path className="road-muted" d="M349 164c-4 27-2 56 12 84" />
        <circle className="route-stop" cx="120" cy="92" r="10" /><circle className="route-stop" cx="254" cy="124" r="7" /><circle className="route-stop" cx="347" cy="164" r="7" /><circle className="route-stop" cx="473" cy="315" r="7" /><circle className="route-stop end" cx="525" cy="425" r="10" />
      </svg>
      <div className="map-legend"><span className="legend-route" />VibeTrip route <span className="legend-time">{formatDuration(routeStats?.driveMinutes || 229)}</span></div>
    </div>
  );
}

export function LiveRouteLoading({ from, to }) {
  return <div className="map-loading" aria-live="polite" aria-busy="true"><div className="map-loading-icon"><Icon name="map" size={18} /></div><strong>Finding your live route</strong><span>{from} → {to}</span><small>Checking traffic, route stops, and nearby places</small></div>;
}
