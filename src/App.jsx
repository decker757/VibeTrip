import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import GoogleRouteMap from './GoogleRouteMap';

const PLANNER_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const navItems = [
  { label: 'Plan a trip', icon: 'compass' },
  { label: 'Explore', icon: 'sparkles' },
  { label: 'Saved trips', icon: 'bookmark', count: '3' },
];

const initialStops = [
  { time: '08:10', title: 'Coffee stop', place: 'The Coffee Exchange', detail: 'Providence, RI', type: 'coffee', duration: '25 min' },
  { time: '10:55', title: 'Fuel up', place: 'Shell · Exit 8', detail: 'New Haven, CT', type: 'fuel', duration: '15 min' },
  { time: '12:30', title: 'Lunch with a view', place: 'The Lobster Shack', detail: 'Mystic, CT', type: 'lunch', duration: '55 min' },
  { time: '15:40', title: 'Check-in', place: 'The Hoxton, Williamsburg', detail: 'Brooklyn, NY', type: 'stay', duration: 'overnight' },
];

const initialCandidates = [
  { id: 'demo-coffee', name: 'The Coffee Exchange', category: 'Cafe', address: 'Providence, RI', rating: 4.6, review_count: 825, price_label: '$', cost_type: 'food', estimated_cost_sgd: 12, cost_label: '~SGD 12/person', cost_note: 'Estimated from Google price level.', detour_minutes: 3, enjoyment_score: 86, crowd_risk: 'low', open_now: true, recommendation_scope: 'along_route', recommendation_kind: 'practical', reason: 'A calm reset with strong reviews and almost no route drift.' },
  { id: 'demo-lunch', name: 'The Lobster Shack', category: 'Restaurant', address: 'Mystic, CT', rating: 4.5, review_count: 1100, price_label: '$$', cost_type: 'food', estimated_cost_sgd: 22, cost_label: '~SGD 22/person', cost_note: 'Estimated from Google price level.', detour_minutes: 12, enjoyment_score: 88, crowd_risk: 'medium', open_now: true, recommendation_scope: 'along_route', recommendation_kind: 'practical', reason: 'Best balance of a memorable meal, student budget, and route fit.' },
  { id: 'demo-attraction', name: 'Mystic Seaport Museum', category: 'Tourist attraction', address: 'Mystic, CT', rating: 4.7, review_count: 3200, price_label: '$$', cost_type: 'admission', estimated_cost_sgd: null, cost_label: 'Ticket price to verify', cost_note: 'Check the official site before committing.', detour_minutes: 14, enjoyment_score: 81, crowd_risk: 'high', open_now: true, recommendation_scope: 'along_route', recommendation_kind: 'scenic', reason: 'High delight potential, but arrive before the afternoon crowd.' },
  { id: 'demo-fuel', name: 'Shell · Exit 8', category: 'Gas station', address: 'New Haven, CT', rating: 4.1, review_count: 410, price_label: '$', cost_type: 'none', estimated_cost_sgd: 0, cost_label: 'No entry cost expected', cost_note: 'Fuel is estimated separately.', detour_minutes: 2, enjoyment_score: 72, crowd_risk: 'low', open_now: true, recommendation_scope: 'along_route', recommendation_kind: 'practical', reason: 'Low-friction fuel and bathroom stop before the final leg.' },
  { id: 'demo-destination', name: 'Brooklyn Bridge Park', category: 'Tourist attraction', address: 'Brooklyn, NY', rating: 4.8, review_count: 8400, price_label: 'Free', cost_type: 'none', estimated_cost_sgd: 0, cost_label: 'Free entry', cost_note: 'Check event schedules before visiting.', detour_minutes: 6, enjoyment_score: 84, crowd_risk: 'high', open_now: true, recommendation_scope: 'destination', recommendation_kind: 'scenic', reason: 'A free destination highlight with skyline views.' },
];

const profileOptions = [
  { id: 'local-gems', label: 'Local gems', icon: 'sparkles' },
  { id: 'slow-mornings', label: 'Slow mornings', icon: 'clock' },
  { id: 'student-budget', label: 'Student budget', icon: 'wallet' },
  { id: 'adventurous', label: 'More adventure', icon: 'compass' },
];

const routeModeOptions = [
  { id: 'fastest', label: 'Fastest', description: 'Bare essentials' },
  { id: 'balanced', label: 'Balanced', description: 'Worthwhile detours' },
  { id: 'scenic', label: 'Scenic', description: 'Intermediate gems' },
];

const defaultCostBreakdown = {
  estimated_total_sgd: 0,
  estimated_per_person_sgd: 0,
  travellers: 4,
  items: [],
  unknown_admissions: [],
  assumptions: [],
};

function Icon({ name, size = 18 }) {
  const paths = {
    arrow: <><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>,
    arrowUp: <><path d="m12 19V5" /><path d="m5 12 7-7 7 7" /></>,
    bookmark: <path d="M6 4.75A1.75 1.75 0 0 1 7.75 3h8.5A1.75 1.75 0 0 1 18 4.75V21l-6-3.5L6 21V4.75Z" />,
    calendar: <><rect x="3" y="4.5" width="18" height="17" rx="2" /><path d="M16 2.5v4M8 2.5v4M3 9h18" /></>,
    check: <path d="m5 12 4.2 4.2L19 6.5" />,
    chevron: <path d="m9 18 6-6-6-6" />,
    clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3.5 2" /></>,
    close: <><path d="m6 6 12 12M18 6 6 18" /></>,
    compass: <><circle cx="12" cy="12" r="9" /><path d="m15.5 8.5-2.1 4.9-4.9 2.1 2.1-4.9 4.9-2.1Z" /></>,
    edit: <><path d="m4 16.5-.8 4.3 4.3-.8L19 8.5 15.5 5 4 16.5Z" /><path d="m13.5 7 3.5 3.5" /></>,
    fuel: <><path d="M4 20V5a2 2 0 0 1 2-2h7v17" /><path d="M4 8h9M8 12h5" /><path d="M13 20h5a2 2 0 0 0 2-2v-6.5L18 9h-2" /><path d="M18 9V5.5A1.5 1.5 0 0 0 16.5 4" /></>,
    grid: <><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" /></>,
    help: <><circle cx="12" cy="12" r="9" /><path d="M9.7 9a2.4 2.4 0 0 1 4.6 1c0 1.7-2.3 2.1-2.3 3.4M12 16.5h.01" /></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 12 9 5 9-5M3 16l9 5 9-5" /></>,
    map: <><path d="m9 18-6 3V6l6-3 6 3 6-3v15l-6 3-6-3Z" /><path d="M9 3v15M15 6v15" /></>,
    menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
    moon: <path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.8a8.6 8.6 0 1 0 11 10.7Z" />,
    plus: <><path d="M12 5v14M5 12h14" /></>,
    search: <><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 4.5 4.5" /></>,
    send: <><path d="m4 4 16 8-16 8 3-8-3-8Z" /><path d="M7 12h13" /></>,
    sparkles: <><path d="m12 3 1.1 4.2L17 9l-3.9 1.8L12 15l-1.1-4.2L7 9l3.9-1.8L12 3ZM19 14l.6 2.4L22 17l-2.4.6L19 20l-.6-2.4L16 17l2.4-.6L19 14ZM5 15l.7 2.3L8 18l-2.3.7L5 21l-.7-2.3L2 18l2.3-.7L5 15Z" /></>,
    suitcase: <><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2" /></>,
    sun: <><circle cx="12" cy="12" r="3.5" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
    users: <><path d="M16 20v-1.5a3.5 3.5 0 0 0-3.5-3.5h-5A3.5 3.5 0 0 0 4 18.5V20" /><circle cx="10" cy="7.5" r="3.5" /><path d="M16 4.3a3.5 3.5 0 0 1 0 6.7M20 20v-1.5a3.5 3.5 0 0 0-2.5-3.4" /></>,
    wallet: <><path d="M4 6.5A2.5 2.5 0 0 1 6.5 4H19v16H6.5A2.5 2.5 0 0 1 4 17.5v-11Z" /><path d="M4 8h15v4h-3a2 2 0 1 0 0 4h3" /></>,
  };
  return <svg aria-hidden="true" className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

function RouteMap({ candidates = [], from = 'Boston, MA', to = 'New York, NY', routeStats }) {
  const markerPositions = [[30, 22], [43, 37], [55, 53], [67, 68]];
  return (
    <div className="map-canvas" aria-label="Map preview of the route from Boston to New York">
      <div className="map-controls">
        <button className="map-button active" aria-label="Map view"><Icon name="map" size={16} /></button>
        <button className="map-button" aria-label="Layers"><Icon name="layers" size={16} /></button>
      </div>
      <div className="map-zoom"><button aria-label="Zoom in"><Icon name="plus" size={16} /></button><button aria-label="Zoom out"><span>−</span></button></div>
      <div className="map-label label-boston">{from.split(',')[0].toUpperCase()}</div>
      <div className="map-label label-providence">PROVIDENCE</div>
      <div className="map-label label-newhaven">NEW HAVEN</div>
      <div className="map-label label-nyc">{to.split(',')[0].toUpperCase()}</div>
      {candidates.slice(0, 4).map((candidate, index) => {
        const [left, top] = markerPositions[index];
        return <button className="map-place" key={candidate.id} style={{ left: `${left}%`, top: `${top}%` }} aria-label={`${candidate.name}, ${candidate.enjoyment_score} enjoyment score`} title={`${candidate.name} · ${candidate.detour_minutes} min detour`}><Icon name="sparkles" size={12} /></button>;
      })}
      <svg className="route-art" viewBox="0 0 800 500" preserveAspectRatio="none" role="presentation">
        <path className="water-shape" d="M555 0c-11 47-7 82 12 113 17 28 20 56 10 83-11 29-5 63 18 95 26 36 44 66 45 111l160 98V0H555Z" />
        <path className="state-line" d="M286 54c-40 44-59 102-63 157-3 52 26 64 50 94 22 28 22 73 58 91 28 14 80-2 111-27 32-25 54-39 71-80 12-29 13-69-5-107-20-42-20-80-8-128" />
        <path className="state-line thin" d="M125 143c51 12 92 15 132 13M275 311c71 18 126 22 188 9M364 55c23 42 49 60 86 71M147 367c56-15 105-4 145 26" />
        <path className="road-muted" d="M120 92C188 110 267 126 347 164c73 35 103 80 126 151 13 39 23 81 52 110" />
        <path className="route-line" d="M120 92C188 110 267 126 347 164c73 35 103 80 126 151 13 39 23 81 52 110" />
        <path className="road-muted" d="M349 164c-4 27-2 56 12 84" />
        <circle className="route-stop" cx="120" cy="92" r="10" />
        <circle className="route-stop" cx="254" cy="124" r="7" />
        <circle className="route-stop" cx="347" cy="164" r="7" />
        <circle className="route-stop" cx="473" cy="315" r="7" />
        <circle className="route-stop end" cx="525" cy="425" r="10" />
      </svg>
      <div className="map-legend"><span className="legend-route" />VibeTrip route <span className="legend-time">{formatDuration(routeStats?.driveMinutes || 229)}</span></div>
    </div>
  );
}

function LiveRouteLoading({ from, to }) {
  return <div className="map-loading" aria-live="polite" aria-busy="true"><div className="map-loading-icon"><Icon name="map" size={18} /></div><strong>Finding your live route</strong><span>{from} → {to}</span><small>Checking traffic, route stops, and nearby places</small></div>;
}

function LocationField({ label, value, onChange, icon }) {
  const fieldRef = useRef(null);
  const [suggestions, setSuggestions] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isFocused, setIsFocused] = useState(false);

  useEffect(() => {
    const query = value.trim();
    if (query.length < 2) {
      setSuggestions([]);
      return undefined;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setIsSearching(true);
      try {
        const response = await fetch(`${PLANNER_API_URL}/places/autocomplete?q=${encodeURIComponent(query)}`, { signal: controller.signal });
        if (!response.ok) throw new Error('Autocomplete unavailable');
        const result = await response.json();
        setSuggestions(result.suggestions || []);
      } catch (error) {
        if (error.name !== 'AbortError') setSuggestions([]);
      } finally {
        setIsSearching(false);
      }
    }, 240);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [value]);

  return (
    <div
      ref={fieldRef}
      className="location-field-wrap"
      onBlur={(event) => {
        if (!fieldRef.current?.contains(event.relatedTarget)) {
          setIsFocused(false);
          setSuggestions([]);
        }
      }}
    >
      <label className="location-field">
        <span className="field-label">{label}</span>
        <span className="field-row"><span className={`location-dot ${icon}`} /> <input aria-label={label} value={value} onFocus={() => setIsFocused(true)} onChange={(event) => onChange(event.target.value)} /></span>
      </label>
      {isFocused && (isSearching || suggestions.length > 0) && <div className="location-suggestions" role="listbox" aria-label={`${label} suggestions`}>
        {isSearching && <div className="location-suggestion muted">Searching cities…</div>}
        {suggestions.map((suggestion) => <button className="location-suggestion" type="button" role="option" key={suggestion.id} onMouseDown={(event) => event.preventDefault()} onClick={() => { onChange(suggestion.text); setSuggestions([]); }}><strong>{suggestion.main_text}</strong><span>{suggestion.secondary_text}</span></button>)}
      </div>}
    </div>
  );
}

function StopIcon({ type }) {
  return <span className={`stop-icon stop-${type}`}><Icon name={type === 'fuel' ? 'fuel' : type === 'stay' ? 'suitcase' : type === 'lunch' ? 'sun' : 'compass'} size={16} /></span>;
}

function formatDuration(minutes) {
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${String(remainingMinutes).padStart(2, '0')}m`;
}

function formatDateLabel(value) {
  if (!value) return 'Select dates';
  return new Intl.DateTimeFormat('en-SG', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(`${value}T00:00:00`));
}

function formatMoney(amount) {
  return `SGD ${Number(amount || 0).toFixed(0)}`;
}

function buildGoogleMapsUrl(from, destination, stops) {
  const waypoints = stops
    .filter((stop) => stop.place_id && ['lunch', 'attraction'].includes(stop.type))
    .map((stop) => `${stop.place}${stop.detail && !stop.detail.includes('Along the route') ? `, ${stop.detail}` : ''}`)
    .filter((value, index, values) => values.indexOf(value) === index)
    .slice(0, 3);
  const params = new URLSearchParams({ api: '1', origin: from, destination, travelmode: 'driving' });
  if (waypoints.length > 0) params.set('waypoints', waypoints.join('|'));
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

function buildWazeUrl(destination) {
  return `https://waze.com/ul?q=${encodeURIComponent(destination)}&navigate=yes&utm_source=vibetrip`;
}

function buildClientCostBreakdown(route, candidate, travellers) {
  const distanceKm = Number(route?.distance_km || 0);
  const fuel = Number((distanceKm / 12 * 2.1).toFixed(2));
  const tolls = Number((distanceKm * 0.045).toFixed(2));
  const food = candidate?.cost_type === 'food' ? Number(candidate.estimated_cost_sgd || 0) * travellers : 0;
  const tickets = candidate?.cost_type === 'admission' && candidate.estimated_cost_sgd != null ? Number(candidate.estimated_cost_sgd) : 0;
  const total = Number((fuel + tolls + food + tickets).toFixed(2));
  return {
    currency: 'SGD',
    travellers,
    estimated_total_sgd: total,
    estimated_per_person_sgd: Number((total / Math.max(travellers, 1)).toFixed(2)),
    items: [
      { key: 'fuel', label: 'Fuel', amount_sgd: fuel, detail: `${Math.round(distanceKm)} km at 12 km/L and SGD 2.10/L` },
      { key: 'tolls', label: 'Tolls', amount_sgd: tolls, detail: 'Route-distance estimate; verify local toll rates' },
      { key: 'food', label: 'Food', amount_sgd: food, detail: candidate?.cost_type === 'food' ? `${travellers} travellers × ${formatMoney(candidate.estimated_cost_sgd)}/person` : 'Choose an eatery to add a food estimate' },
      { key: 'tickets', label: 'Known tickets', amount_sgd: tickets, detail: 'Only includes ticket prices available to the planner' },
    ],
    unknown_admissions: candidate?.cost_type === 'admission' && candidate.estimated_cost_sgd == null ? [candidate.name] : [],
    assumptions: ['Fuel, tolls, and food are estimates in SGD.', 'Attraction admission prices must be verified from the venue or official website.'],
  };
}

function itineraryToStops(itinerary, detours, destination) {
  const details = {
    coffee: { place: 'Coffee stop', detail: 'Along the route', type: 'coffee' },
    fuel: { place: 'Fuel + bathroom', detail: 'On-route station', type: 'fuel' },
    stay: { place: 'Destination check-in', detail: destination, type: 'stay' },
  };

  return itinerary.map((item) => {
    const associatedPlace = detours?.find((candidate) => candidate.id === item.place_id);
    const itemDetails = item.kind === 'coffee'
      ? { place: associatedPlace?.name || 'Coffee stop', detail: associatedPlace?.address || 'Along the route', type: 'coffee' }
      : item.kind === 'fuel'
        ? { place: associatedPlace?.name || 'Fuel + bathroom', detail: associatedPlace?.address || 'On-route station', type: 'fuel' }
        : item.kind === 'meal'
      ? { place: associatedPlace?.name || item.title, detail: associatedPlace?.address || 'Along the route', type: 'lunch' }
      : item.kind === 'attraction'
        ? { place: associatedPlace?.name || item.title, detail: associatedPlace?.address || 'Scenic stop along the route', type: 'attraction' }
        : details[item.kind] || details.coffee;
    return {
      time: item.time,
      title: item.title,
      place_id: item.place_id,
      location: associatedPlace?.location,
      duration_minutes: item.duration_min || 0,
      duration: item.duration_min ? `${item.duration_min} min` : 'overnight',
      ...itemDetails,
    };
  });
}

function candidateToStop(candidate, time = '12:30') {
  const category = candidate.category?.toLowerCase() || '';
  return {
    time,
    title: candidate.name,
    place: candidate.name,
    detail: candidate.address || 'Along the route',
    type: category.includes('cafe') || category.includes('coffee') ? 'coffee' : category.includes('gas') || category.includes('fuel') || category.includes('convenience') || category.includes('store') ? 'fuel' : category.includes('attraction') ? 'attraction' : 'lunch',
    duration_minutes: 45,
    duration: '45 min',
    place_id: candidate.id,
    location: candidate.location,
  };
}

function timeToMinutes(value = '') {
  const [hours, minutes] = value.split(':').map(Number);
  return Number.isFinite(hours) && Number.isFinite(minutes) ? hours * 60 + minutes : null;
}

function addMinutesToTime(value, minutes) {
  const total = (timeToMinutes(value) ?? 0) + minutes;
  return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

function formatTravelGap(currentStop, nextStop) {
  const current = timeToMinutes(currentStop.time);
  const next = timeToMinutes(nextStop.time);
  if (current == null || next == null) return 'Flexible drive';
  const drivingMinutes = Math.max(0, next - current - (currentStop.duration_minutes || 0));
  if (drivingMinutes < 1) return 'Continue to next stop';
  const hours = Math.floor(drivingMinutes / 60);
  const minutes = drivingMinutes % 60;
  return `${hours ? `${hours}h ` : ''}${minutes ? `${minutes}m` : ''} drive`.trim();
}

function TimelineRow({ stop, index, isLast, isFocused, isEditing, isManaging, onFocus, onChange, onRemove }) {
  return (
    <div className={`timeline-item ${isFocused ? 'focused' : ''} ${isEditing ? 'editing' : ''}`} role="button" tabIndex="0" aria-label={`Focus ${stop.title} on the map`} onClick={() => onFocus(stop, index)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onFocus(stop, index); } }}>
      <div className="timeline-time">{stop.time}</div>
      <div className="timeline-rail"><StopIcon type={stop.type} />{!isLast && <span className="rail-line" />}</div>
      <div className="timeline-copy"><strong>{stop.title}</strong>{isFocused && <span className="timeline-focus-state" aria-live="polite">On map</span>}<span>{stop.place} <i>·</i> {stop.detail}</span></div>
      <span className="stop-duration">{stop.duration === 'overnight' ? 'overnight' : `${stop.duration} stop`}</span>
      <div className="timeline-actions">
        {isManaging && stop.type !== 'stay' && <button className="timeline-remove" title={`Remove ${stop.title}`} onClick={(event) => { event.stopPropagation(); onRemove(index); }}><Icon name="close" size={12} />Remove</button>}
        <button className="timeline-change" title={`Choose a replacement for ${stop.title}`} onClick={(event) => { event.stopPropagation(); onChange(index); }}>{isEditing ? 'Choosing' : 'Change'}</button>
      </div>
    </div>
  );
}

function App() {
  const [from, setFrom] = useState('Boston, MA');
  const [to, setTo] = useState('New York, NY');
  const [stops, setStops] = useState(initialStops);
  const [activeNav, setActiveNav] = useState('Plan a trip');
  const [routeMode, setRouteMode] = useState('balanced');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isRerouting, setIsRerouting] = useState(false);
  const [isGenerated, setIsGenerated] = useState(false);
  const [message, setMessage] = useState('');
  const [plannerSource, setPlannerSource] = useState('demo');
  const [routeStats, setRouteStats] = useState({ driveMinutes: 229, distanceKm: 348, confidence: 94 });
  const [route, setRoute] = useState({});
  const [startDate, setStartDate] = useState('2025-09-14');
  const [endDate, setEndDate] = useState('2025-09-16');
  const [startTime, setStartTime] = useState('08:10');
  const [endTime, setEndTime] = useState('18:00');
  const [travellers, setTravellers] = useState(4);
  const [budgetPerPerson, setBudgetPerPerson] = useState(400);
  const [adventureLevel, setAdventureLevel] = useState(70);
  const [preferences, setPreferences] = useState(['adventurous', 'local-gems', 'slow-mornings', 'student-budget']);
  const [candidatePlaces, setCandidatePlaces] = useState(initialCandidates);
  const [selectedPlaceId, setSelectedPlaceId] = useState('demo-lunch');
  const [costBreakdown, setCostBreakdown] = useState(() => buildClientCostBreakdown({ distance_km: 348 }, initialCandidates[1], 4));
  const [editingStopIndex, setEditingStopIndex] = useState(null);
  const [focusedStopIndex, setFocusedStopIndex] = useState(null);
  const [isManagingStops, setIsManagingStops] = useState(false);
  const [placeQuery, setPlaceQuery] = useState('');
  const [placeSearchResults, setPlaceSearchResults] = useState([]);
  const [hasSearchedPlaces, setHasSearchedPlaces] = useState(false);
  const [isSearchingPlaces, setIsSearchingPlaces] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simulationResult, setSimulationResult] = useState(null);
  const hasAutoGeneratedRef = useRef(false);
  const mapControllerRef = useRef(null);

  const routeTitle = useMemo(() => `${from.split(',')[0]} → ${to.split(',')[0]}`, [from, to]);
  const defaultReplacementIndex = Math.max(0, stops.findIndex((stop) => stop.type === 'lunch'));
  const replacementStopIndex = editingStopIndex ?? focusedStopIndex ?? defaultReplacementIndex;
  const displayedCandidates = useMemo(() => candidatePlaces.slice(0, routeMode === 'fastest' ? 4 : 6), [candidatePlaces, routeMode]);
  const mapCandidates = useMemo(() => {
    const visibleIds = new Set(displayedCandidates.map((candidate) => candidate.id));
    const waypointIds = new Set([
      ...stops.map((stop) => stop.place_id).filter(Boolean),
      ...(route.routed_waypoint_ids || []),
    ]);
    return candidatePlaces.filter((candidate) => visibleIds.has(candidate.id) || waypointIds.has(candidate.id));
  }, [candidatePlaces, displayedCandidates, route.routed_waypoint_ids, stops]);
  const googleMapsUrl = useMemo(() => buildGoogleMapsUrl(from, to, stops), [from, to, stops]);
  const wazeUrl = useMemo(() => buildWazeUrl(to), [to]);
  const profileSummary = adventureLevel >= 70 ? 'Curious, not rushed.' : adventureLevel <= 35 ? 'Easygoing, well paced.' : 'Balanced, open to detours.';
  const profileBalance = adventureLevel >= 70 ? 'More adventurous' : adventureLevel <= 35 ? 'More laid back' : 'Balanced pace';

  async function generateTrip() {
    if (isGenerating) return;
    setIsGenerating(true);
    setMessage('');

    if (!from.trim() || !to.trim()) {
      setMessage('Add both a starting city and destination before planning.');
      setIsGenerating(false);
      return;
    }
    if (endDate < startDate) {
      setMessage('The return date must be on or after the departure date.');
      setIsGenerating(false);
      return;
    }
    if (startDate === endDate && endTime <= startTime) {
      setMessage('Choose a target end time later than the start time for a same-day trip.');
      setIsGenerating(false);
      return;
    }

    const request = {
      start: from,
      destination: to,
      travellers,
      budget_per_person: budgetPerPerson,
      dates: `${startDate}/${endDate}`,
      start_date: startDate,
      end_date: endDate,
      start_time: startTime,
      end_time: endTime,
      preferences,
      adventure_level: adventureLevel,
      route_mode: routeMode,
    };

    try {
      const response = await fetch(`${PLANNER_API_URL}/trips/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });

      if (!response.ok) throw new Error(`Planner returned ${response.status}`);

      const result = await response.json();
      const candidates = result.candidate_places?.length ? result.candidate_places : initialCandidates;
      setCandidatePlaces(candidates);
      setSelectedPlaceId(result.selected_places?.[0]?.id || candidates[0]?.id || 'demo-lunch');
      setRoute(result.route || {});
      setStops(itineraryToStops(result.itinerary || [], candidates, result.destination));
      setRouteStats({
        driveMinutes: result.route?.drive_minutes || 229,
        distanceKm: result.route?.distance_km || 348,
        confidence: result.confidence || 94,
      });
      setCostBreakdown(result.cost_breakdown || buildClientCostBreakdown(result.route, candidates[0], travellers));
      setPlannerSource('api');
      setIsGenerated(true);
      setMessage(result.warning || `${routeModeOptions.find((option) => option.id === routeMode)?.label} route ready — recommendations balance route fit, budget, ratings, and opening hours.`);
    } catch {
      // The local preview keeps the MVP usable when FastAPI is not running yet.
      setPlannerSource('demo');
      setCandidatePlaces(initialCandidates);
      setSelectedPlaceId('demo-lunch');
      setRoute({});
      setCostBreakdown(buildClientCostBreakdown({ distance_km: 348 }, initialCandidates[1], travellers));
      window.setTimeout(() => {
        setIsGenerated(true);
        setMessage('API unavailable — loaded a local preview so you can keep exploring.');
      }, 350);
    } finally {
      setIsGenerating(false);
    }
  }

  useEffect(() => {
    if (hasAutoGeneratedRef.current) return;
    hasAutoGeneratedRef.current = true;
    generateTrip();
  }, []);

  async function rerouteDraft(nextStops, successMessage) {
    if (isRerouting) return;
    setIsRerouting(true);
    try {
      const response = await fetch(`${PLANNER_API_URL}/trips/reroute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start: from,
          destination: to,
          start_time: startTime,
          budget_per_person: budgetPerPerson,
          route_mode: routeMode,
          route,
          stops: nextStops.filter((stop) => stop.type !== 'stay' && stop.place_id).map((stop) => ({ id: stop.place_id, location: stop.location })),
        }),
      });
      if (!response.ok) throw new Error(`Reroute returned ${response.status}`);
      const result = await response.json();
      const nextRoute = result.route || {};
      setRoute(nextRoute);
      setRouteStats((current) => ({
        driveMinutes: nextRoute.drive_minutes || current.driveMinutes,
        distanceKm: nextRoute.distance_km || current.distanceKm,
        confidence: current.confidence,
      }));
      setPlannerSource(result.provider === 'google' ? 'api' : 'demo');
      setMessage(result.warning || successMessage);
    } catch {
      setMessage(`${successMessage} The map could not recalculate right now; try again when the route service is available.`);
    } finally {
      setIsRerouting(false);
    }
  }

  function addStop() {
    const existingIds = new Set(stops.map((stop) => stop.place_id).filter(Boolean));
    const candidate = candidatePlaces.find((item) => !existingIds.has(item.id) && item.recommendation_scope === 'along_route') || candidatePlaces.find((item) => !existingIds.has(item.id));
    if (!candidate) {
      setMessage('No unused route suggestions are available yet. Ask the route agent for another place.');
      return;
    }
    const checkInIndex = stops.findIndex((stop) => stop.type === 'stay');
    const previousStop = stops[Math.max(0, checkInIndex - 1)] || stops[stops.length - 1];
    const time = previousStop?.time ? addMinutesToTime(previousStop.time, (previousStop.duration_minutes || 45) + 30) : startTime;
    const next = candidateToStop(candidate, time);
    const destinationIndex = stops.findIndex((stop) => stop.type === 'stay');
    const nextStops = destinationIndex < 0
      ? [...stops, next]
      : [...stops.slice(0, destinationIndex), next, ...stops.slice(destinationIndex)];
    setStops(nextStops);
    setIsManagingStops(true);
    void rerouteDraft(nextStops, `${candidate.name} added and the route was recalculated through it.`);
  }

  function selectCandidate(candidate) {
    const targetIndex = replacementStopIndex;
    const nextStops = stops.map((stop, index) => index === targetIndex ? candidateToStop(candidate, stop.time) : stop);
    setSelectedPlaceId(candidate.id);
    setStops(nextStops);
    setFocusedStopIndex(targetIndex);
    setEditingStopIndex(null);
    setIsManagingStops(true);
    setCostBreakdown(buildClientCostBreakdown(route, candidate, travellers));
    void rerouteDraft(nextStops, `${candidate.name} selected and the route was recalculated through it.`);
  }

  function beginStopChange(index) {
    setIsManagingStops(true);
    setEditingStopIndex(index);
    setFocusedStopIndex(index);
    setMessage(`Choose a nearby route alternative for ${stops[index]?.title || 'this stop'}.`);
  }

  function chooseReplacementStop(event) {
    const index = Number(event.target.value);
    setEditingStopIndex(index);
    setFocusedStopIndex(index);
    setIsManagingStops(true);
    setMessage(`New place requests will replace ${stops[index]?.title || 'this stop'}.`);
  }

  function removeStop(index) {
    const removed = stops[index];
    const nextStops = stops.filter((_, stopIndex) => stopIndex !== index);
    setStops(nextStops);
    setEditingStopIndex(null);
    setFocusedStopIndex(null);
    void rerouteDraft(nextStops, `${removed?.title || 'Stop'} removed and the route was recalculated.`);
  }

  function toggleStopManager() {
    setIsManagingStops((current) => !current);
    setEditingStopIndex(null);
    setMessage(isManagingStops ? 'Stop changes are saved in this draft.' : 'Choose Change or Remove on a timeline stop.');
  }

  async function searchRoutePlaces(event) {
    event.preventDefault();
    const query = placeQuery.trim();
    if (query.length < 3 || isSearchingPlaces) return;
    setIsSearchingPlaces(true);
    setPlaceSearchResults([]);
    setHasSearchedPlaces(false);
    try {
      const response = await fetch(`${PLANNER_API_URL}/trips/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start: from, destination: to, query, budget_per_person: budgetPerPerson, crowd_tolerance: preferences.includes('student-budget') ? 'low' : 'medium', route_mode: routeMode }),
      });
      if (!response.ok) throw new Error(`Search returned ${response.status}`);
      const result = await response.json();
      setPlaceSearchResults(result.candidate_places || []);
      setHasSearchedPlaces(true);
      setCandidatePlaces((current) => [...(result.candidate_places || []), ...current.filter((candidate) => !(result.candidate_places || []).some((match) => match.id === candidate.id))]);
      setMessage(result.warning || `Found ${result.candidate_places?.length || 0} route matches for “${query}”.`);
    } catch {
      const terms = query.toLowerCase().split(/\s+/).filter((term) => term.length > 2);
      const cuisine = ['chinese', 'japanese', 'korean', 'thai', 'indian', 'malay', 'vietnamese', 'mexican', 'italian', 'mediterranean'].find((term) => terms.includes(term));
      const localMatches = candidatePlaces.filter((candidate) => {
        const haystack = `${candidate.name} ${candidate.category} ${candidate.reason}`.toLowerCase();
        return cuisine ? haystack.includes(cuisine) : terms.some((term) => haystack.includes(term));
      });
      setPlaceSearchResults(localMatches);
      setHasSearchedPlaces(true);
      setMessage(localMatches.length ? 'Showing local route matches while the search service is unavailable.' : 'The route search is unavailable. Try a broader description.');
    } finally {
      setIsSearchingPlaces(false);
    }
  }

  function togglePreference(preference) {
    setPreferences((current) => current.includes(preference) ? current.filter((item) => item !== preference) : [...current, preference]);
  }

  function updateAdventureLevel(event) {
    const nextLevel = Number(event.target.value);
    setAdventureLevel(nextLevel);
  }

  function commitAdventureLevel(event) {
    const nextLevel = Number(event.target.value);
    setMessage(`${nextLevel}% adventurous · ${nextLevel >= 70 ? 'more local gems and scenic detours' : nextLevel <= 35 ? 'more practical stops and buffer' : 'a balanced mix of both'}. Generate the route to apply it.`);
  }

  async function simulateTrip(event) {
    if (isSimulating) return;
    setIsSimulating(true);
    setSimulationResult(null);
    const currentStopIndex = replacementStopIndex;
    const currentStop = stops[currentStopIndex] || stops[2];
    const itinerary = stops.map((stop) => ({
      time: stop.time,
      title: stop.title,
      kind: stop.type === 'lunch' ? 'meal' : stop.type,
      duration_min: Number.parseInt(stop.duration, 10) || 0,
      place_id: stop.place_id,
    }));
    try {
      const response = await fetch(`${PLANNER_API_URL}/trips/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ destination: to, current_stop_id: currentStop?.place_id || selectedPlaceId, current_stop_title: currentStop?.title || 'Lunch with a view', current_stop_index: currentStopIndex, event, candidates: candidatePlaces, itinerary }),
      });
      if (!response.ok) throw new Error(`Simulation returned ${response.status}`);
      const result = await response.json();
      setSimulationResult(result);
      setMessage(result.message);
      if (result.replacement) {
        const nextStops = stops.map((stop, index) => index === currentStopIndex ? candidateToStop(result.replacement, stop.time) : stop);
        setStops(nextStops);
        setSelectedPlaceId(result.replacement.id);
        void rerouteDraft(nextStops, `${result.replacement.name} is now in the route.`);
      } else if (result.action === 'go_to_destination') {
        const nextStops = stops.filter((_, index) => index !== currentStopIndex);
        setStops(nextStops);
        void rerouteDraft(nextStops, `Removed ${currentStop?.title || 'the unavailable stop'} and recalculated the route.`);
      }
    } catch {
      const backup = candidatePlaces.find((candidate) => candidate.id !== currentStop?.place_id && candidate.open_now && (event !== 'crowded' || candidate.crowd_risk !== 'high'));
      const result = backup
        ? { action: 'replace_stop', replacement: backup, message: `Local simulation: swapped in ${backup.name} as the next best fit.` }
        : { action: 'go_to_destination', message: `Local simulation: continue to ${to}.` };
      setSimulationResult(result);
      setMessage(result.message);
      if (backup) {
        const nextStops = stops.map((stop, index) => index === currentStopIndex ? candidateToStop(backup, stop.time) : stop);
        setStops(nextStops);
        setSelectedPlaceId(backup.id);
        void rerouteDraft(nextStops, `${backup.name} is now in the route.`);
      } else {
        const nextStops = stops.filter((_, index) => index !== currentStopIndex);
        setStops(nextStops);
        void rerouteDraft(nextStops, `Removed ${currentStop?.title || 'the unavailable stop'} and recalculated the route.`);
      }
    } finally {
      setIsSimulating(false);
    }
  }

  function swapLocations() {
    setFrom(to);
    setTo(from);
    setMessage('Direction swapped.');
  }

  function focusTimelineStop(stop, index) {
    setFocusedStopIndex(index);
    const focused = mapControllerRef.current?.focusStop(stop);
    const mapCard = document.querySelector('.map-card');
    if (mapCard && (mapCard.getBoundingClientRect().top < 0 || mapCard.getBoundingClientRect().bottom > window.innerHeight)) {
      mapCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    setMessage(focused ? `${stop.title} focused on the map.` : `${stop.title} selected. Generate a live route to focus it on the map.`);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark"><span /></span><span>vibetrip</span></div>
        <div className="sidebar-section-label">Workspace</div>
        <nav className="main-nav" aria-label="Main navigation">
          {navItems.map((item) => (
            <button key={item.label} className={`nav-item ${activeNav === item.label ? 'active' : ''}`} onClick={() => setActiveNav(item.label)}>
              <Icon name={item.icon} size={17} /><span>{item.label}</span>{item.count && <span className="nav-count">{item.count}</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-section-label sidebar-bottom-label">Your setup</div>
        <nav className="main-nav" aria-label="Account navigation">
          <button className="nav-item" onClick={() => setMessage('Profile settings are coming next.') }><Icon name="users" size={17} /><span>Travel profile</span></button>
          <button className="nav-item" onClick={() => setMessage('Preferences saved locally for this prototype.') }><Icon name="settings" size={17} /><span>Preferences</span></button>
        </nav>
        <div className="sidebar-footer">
          <div className="tip-card"><div className="tip-icon"><Icon name="sparkles" size={15} /></div><p><strong>Trip tip</strong><br />Leave 20% of the day unplanned. That’s where the good stuff happens.</p></div>
          <button className="profile-button"><span className="avatar">ET</span><span className="profile-copy"><strong>Ernest Tan</strong><small>Singapore · NUS</small></span><Icon name="chevron" size={15} /></button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <button className="mobile-menu" aria-label="Open navigation"><Icon name="menu" size={20} /></button>
          <div className="breadcrumbs"><span>My trips</span><Icon name="chevron" size={13} /><strong>New trip</strong></div>
          <div className="topbar-actions"><span className="save-status"><span className="status-dot" />All changes saved</span><button className="icon-button" aria-label="Help"><Icon name="help" size={18} /></button><button className="icon-button" aria-label="Settings"><Icon name="settings" size={18} /></button></div>
        </header>

        <div className="content-wrap">
          <section className="page-intro">
            <div><p className="eyebrow">NEW TRIP <span>·</span> 01</p><h1>Make the way there<br /><em>part of the story.</em></h1><p className="intro-copy">Tell us where you’re going. We’ll find the route that gets you there with enough room to actually enjoy it.</p></div>
            <div className="intro-side"><div className="agent-orbit"><span className="orbit-dot one" /><span className="orbit-dot two" /><span className="orbit-dot three" /><Icon name="sparkles" size={19} /></div><span>4 agents ready<br /><small>for your first draft</small></span></div>
          </section>

          <section className="profile-card top-profile-card">
            <div className="card-heading"><div><p className="eyebrow">TRAVEL PROFILE</p><h3>{profileSummary}</h3></div><span className="profile-helper">Used by the route and detour agents</span></div>
            <div className="profile-tags">{profileOptions.map((option) => <button type="button" className={`profile-tag-button ${preferences.includes(option.id) ? 'active' : ''}`} key={option.id} onClick={() => togglePreference(option.id)}><Icon name={option.icon} size={14} />{option.label}</button>)}</div>
            <div className="profile-meter"><div className="meter-labels"><span>ADVENTUROUS</span><span>LAID BACK</span></div><input id="travel-profile-adventure" className="meter-input" type="range" min="0" max="100" step="1" value={adventureLevel} onInput={updateAdventureLevel} onChange={commitAdventureLevel} style={{ '--meter-level': `${adventureLevel}%` }} aria-label="Travel profile balance between adventurous and laid back" /><div className="meter-track" aria-hidden="true" /><div className="meter-caption" aria-live="polite"><span>{profileBalance}</span><strong>{adventureLevel}%</strong></div></div>
          </section>

          <section className="planner-card">
            <div className="planner-fields">
              <LocationField label="STARTING FROM" value={from} onChange={setFrom} icon="start" />
              <button className="swap-button" onClick={swapLocations} aria-label="Swap starting point and destination"><Icon name="arrow" size={16} /></button>
              <LocationField label="DESTINATION" value={to} onChange={setTo} icon="end" />
            </div>
            <div className="planner-divider" />
            <div className="route-mode-selector" aria-label="Route style">
              <div className="route-mode-heading"><span><small>ROUTE STYLE</small><strong>How much should the way there matter?</strong></span><span className="route-mode-helper">Changes the stops and recommendations</span></div>
              <div className="route-mode-options">{routeModeOptions.map((option) => <button type="button" key={option.id} className={`route-mode-option ${routeMode === option.id ? 'active' : ''}`} aria-pressed={routeMode === option.id} onClick={() => { setRouteMode(option.id); setMessage(`${option.label} route selected. Generate the route to update recommendations.`); }}><span>{option.label}</span><small>{option.description}</small></button>)}</div>
            </div>
            <div className="planner-options">
              <label className="option-chip date-chip"><Icon name="calendar" size={15} /><span><small>DATES</small><span className="date-inputs"><input aria-label="Departure date" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /><span>—</span><input aria-label="Return date" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></span></span></label>
              <label className="option-chip start-time-chip"><Icon name="clock" size={15} /><span><small>START TIME</small><input aria-label="Start time" type="time" value={startTime} onChange={(event) => setStartTime(event.target.value)} /></span></label>
              <label className="option-chip start-time-chip"><Icon name="clock" size={15} /><span><small>TARGET END</small><input aria-label="Target end time" type="time" value={endTime} onChange={(event) => setEndTime(event.target.value)} /></span></label>
              <label className="option-chip number-chip"><Icon name="users" size={15} /><span><small>TRAVELLERS</small><input aria-label="Travellers" type="number" min="1" max="12" value={travellers} onChange={(event) => setTravellers(Math.min(12, Math.max(1, Number(event.target.value) || 1)))} /><b>students</b></span></label>
              <label className="option-chip number-chip"><Icon name="wallet" size={15} /><span><small>BUDGET / PERSON</small><span className="money-input"><b>SGD</b><input aria-label="Budget per person" type="number" min="0" step="10" value={budgetPerPerson} onChange={(event) => setBudgetPerPerson(Math.max(0, Number(event.target.value) || 0))} /></span></span></label>
              <button className={`generate-button ${isGenerating ? 'loading' : ''}`} onClick={generateTrip} disabled={isGenerating}><span>{isGenerating ? 'Building your route' : isGenerated ? 'Regenerate route' : 'Make my route'}</span>{isGenerating ? <span className="button-loader" /> : <Icon name="arrow" size={17} />}</button>
            </div>
          </section>

          {message && <div className="live-message" role="status"><Icon name="check" size={15} />{message}</div>}

          <section className="route-section">
            <div className="section-heading"><div><p className="eyebrow">YOUR FIRST DRAFT <span>·</span> {isGenerating ? 'BUILDING LIVE ROUTE' : plannerSource === 'api' ? 'LANGGRAPH' : 'LOCAL PREVIEW'}</p><h2>{routeTitle}</h2></div><div className="route-meta"><span className="route-mode-meta"><Icon name="compass" size={15} />{route.route_mode_label || routeModeOptions.find((option) => option.id === routeMode)?.label} route</span><span><Icon name="clock" size={15} />{isGenerating ? 'checking time' : `${formatDuration(routeStats.driveMinutes)} drive`}</span><span><Icon name="map" size={15} />{isGenerating ? 'checking distance' : `${routeStats.distanceKm} km`}</span>{route.estimated_arrival_time && <span><Icon name="check" size={15} />arrive around {route.estimated_arrival_time}</span>}{route.traffic_status && <span className={`traffic-indicator ${route.traffic_status}`}><span />{route.traffic_status} traffic {route.traffic_delay_minutes ? `+${route.traffic_delay_minutes}m` : ''}</span>}<span className="route-export-actions" aria-label="Export route"><a className="route-export-link" href={googleMapsUrl} target="_blank" rel="noreferrer" title="Open this route with stops in Google Maps"><Icon name="map" size={13} />Google Maps</a><a className="route-export-link" href={wazeUrl} target="_blank" rel="noreferrer" title="Open the destination in Waze"><Icon name="arrow" size={13} />Waze</a></span></div></div>
            <div className="route-grid">
              <div className={`map-card ${isRerouting ? 'rerouting' : ''}`}>{isGenerating ? <LiveRouteLoading from={from} to={to} /> : <GoogleRouteMap ref={mapControllerRef} route={route} candidates={mapCandidates} onSelectCandidate={selectCandidate} fallback={<RouteMap candidates={mapCandidates} from={from} to={to} routeStats={routeStats} />} />}<div className="map-footer"><div><span className="map-footer-label">ROUTE CONFIDENCE</span><strong>{isGenerating || isRerouting ? '—' : `${routeStats.confidence}% · clear and comfortable`}</strong>{route.traffic_status && <small className="traffic-footnote">{route.traffic_note} · Construction alerts not connected</small>}{route.waypoint_note && <small className="route-waypoint-note">{route.waypoint_note}</small>}</div><span className="route-badge"><Icon name={isGenerating || isRerouting ? 'clock' : 'check'} size={13} /> {isGenerating ? 'Finding route' : isRerouting ? 'Recalculating route' : 'Efficient detour'}</span></div></div>
              <div className="timeline-card">
                <div className="timeline-top"><div><p className="eyebrow">DAY 01 <span>·</span> {formatDateLabel(startDate)}</p><h3>Easy pace to {to.split(',')[0]}</h3></div><button className={`edit-button ${isManagingStops ? 'active' : ''}`} onClick={toggleStopManager}>{isManagingStops ? 'Done' : 'Manage stops'} <Icon name={isManagingStops ? 'check' : 'edit'} size={15} /></button></div>
                {isManagingStops && <p className="timeline-helper"><Icon name="sparkles" size={13} />Choose a stop to replace or remove it. Route options below update the selected stop.</p>}
                <div className="timeline-list">{isGenerating ? <div className="timeline-loading"><span /><span /><span /></div> : stops.map((stop, index) => <Fragment key={`${stop.title}-${index}`}><TimelineRow stop={stop} index={index} isLast={index === stops.length - 1} isFocused={focusedStopIndex === index} isEditing={editingStopIndex === index} isManaging={isManagingStops} onFocus={focusTimelineStop} onChange={beginStopChange} onRemove={removeStop} />{index < stops.length - 1 && <div className="timeline-gap"><span>{formatTravelGap(stop, stops[index + 1])}</span></div>}</Fragment>)}</div>
                {(route.timeline_note || route.waypoint_note) && <p className="timeline-note"><Icon name="clock" size={13} />{[route.timeline_note, route.waypoint_note].filter(Boolean).join(' · ')}</p>}
                <button className="add-stop" onClick={addStop}><Icon name="plus" size={15} />Add a stop</button>
              </div>
            </div>
            <div className="route-assistant"><div className="assistant-card"><div className="card-heading"><div><p className="eyebrow">ROUTE REQUEST AGENT</p><h3>Ask for a better fit.</h3></div><span className="live-pill"><span />GOOGLE PLACES</span></div><p className="agent-description">Describe the kind of place you want in plain language. VibeTrip searches along this route, scores the matches, and lets you use one in the selected timeline slot.</p><div className="assistant-target"><label htmlFor="replacement-stop">Replace this stop</label><select id="replacement-stop" value={replacementStopIndex} onChange={chooseReplacementStop}>{stops.map((stop, index) => stop.type !== 'stay' && <option value={index} key={`${stop.place_id || stop.title}-${index}`}>{stop.time} · {stop.title}</option>)}</select></div><div className="request-chips"><button type="button" onClick={() => setPlaceQuery('a quiet cafe with a view')}>Quiet cafe with a view</button><button type="button" onClick={() => setPlaceQuery('local food under my budget')}>Local food under budget</button><button type="button" onClick={() => setPlaceQuery('scenic place with low crowd risk')}>Low-crowd scenic stop</button></div><form className="route-request-form" onSubmit={searchRoutePlaces}><input aria-label="Describe a place to find along the route" value={placeQuery} onChange={(event) => setPlaceQuery(event.target.value)} placeholder="e.g. a quiet cafe with a view" /><button type="submit" disabled={isSearchingPlaces || placeQuery.trim().length < 3}>{isSearchingPlaces ? 'Searching…' : 'Find places'}<Icon name={isSearchingPlaces ? 'clock' : 'send'} size={14} /></button></form>{placeSearchResults.length > 0 && <div className="request-results" aria-live="polite"><div className="request-results-heading"><strong>{placeSearchResults.length} route matches</strong><span>Use one for the selected stop</span></div>{placeSearchResults.slice(0, 4).map((candidate) => <div className="request-result" key={candidate.id}><div><strong>{candidate.name}</strong><span>{candidate.category} · {candidate.address}</span><small>★ {Number(candidate.rating || 0).toFixed(1)} · {candidate.detour_minutes} min detour · {candidate.cost_label || candidate.price_label || 'Cost to verify'}</small></div><button type="button" onClick={() => selectCandidate(candidate)}>Use here</button></div>)}</div>}{hasSearchedPlaces && placeSearchResults.length === 0 && <div className="request-empty" role="status">No suitable places found along this route. Try a broader request, such as “Chinese restaurant” or “quiet cafe”.</div>}</div></div>
          </section>

          <section className="intelligence-grid">
            <div className="suggestions-card">
              <div className="card-heading"><div><p className="eyebrow">ROUTE OPTIONS</p><h3>Choose your stops.</h3></div><span className="source-badge"><Icon name="sparkles" size={12} />{plannerSource === 'api' ? 'LIVE PLACES' : 'DEMO DATA'}</span></div>
              <p className="intelligence-copy">{isManagingStops ? 'Choose a place below to replace the selected timeline stop. It will be added to the draft route.' : routeMode === 'fastest' ? 'A short list of practical stops and a few destination ideas, kept close to the fastest route.' : routeMode === 'scenic' ? 'The planner looks across intermediate cities and the destination for places worth shaping the journey around.' : 'The planner balances practical breaks with a small number of worthwhile intermediate and destination recommendations.'}</p>
              <div className="candidate-list">{displayedCandidates.map((candidate) => { const category = candidate.category?.toLowerCase() || ''; const icon = category.includes('restaurant') ? 'sun' : category.includes('gas') || category.includes('fuel') || category.includes('convenience') || category.includes('store') ? 'fuel' : 'sparkles'; return <div className={`candidate-row ${selectedPlaceId === candidate.id ? 'selected' : ''}`} key={candidate.id} title={candidate.review_quote || candidate.reason}><div className="candidate-icon"><Icon name={icon} size={15} /></div><div className="candidate-copy"><strong>{candidate.name}</strong><span>{candidate.category} <i>·</i> {candidate.address}</span><small className="candidate-scope">{candidate.recommendation_scope === 'destination' ? 'At destination' : candidate.recommendation_kind === 'scenic' ? 'Scenic along route' : 'Practical along route'}</small><small><span className="rating-star">★</span> {Number(candidate.rating || 0).toFixed(1)} ({Number(candidate.review_count || 0).toLocaleString()}) <i>·</i> {candidate.detour_minutes} min detour</small><small className="candidate-cost">{candidate.cost_label || candidate.price_label || 'Cost to verify'} {candidate.website_uri && <a href={candidate.website_uri} target="_blank" rel="noreferrer">Official site ↗</a>}</small>{candidate.review_quote && <small className="review-preview">“{candidate.review_quote}”</small>}</div><div className="candidate-score"><strong>{candidate.enjoyment_score}</strong><small>enjoyment</small></div><button className="candidate-use" onClick={() => selectCandidate(candidate)}>{selectedPlaceId === candidate.id ? 'Selected' : isManagingStops ? 'Use here' : 'Use'}</button></div>; })}</div>
            </div>
            <div className="budget-card">
              <div className="card-heading"><div><p className="eyebrow">TRIP BUDGET</p><h3>{formatMoney(costBreakdown.estimated_total_sgd)} total</h3></div><span className="cost-per-person">{formatMoney(costBreakdown.estimated_per_person_sgd)} / person</span></div>
              <p className="intelligence-copy">A transparent estimate for {travellers} travellers. Select another stop to refresh the food or ticket line.</p>
              <div className="cost-list">{(costBreakdown.items || []).map((item) => <div className="cost-row" key={item.key}><span><strong>{item.label}</strong><small>{item.detail}</small></span><b>{formatMoney(item.amount_sgd)}</b></div>)}</div>
              {costBreakdown.unknown_admissions?.length > 0 && <div className="cost-warning"><Icon name="help" size={13} /><span>Verify admission for {costBreakdown.unknown_admissions.join(', ')} before booking.</span></div>}
              <div className="cost-assumptions">{(costBreakdown.assumptions || []).map((assumption) => <small key={assumption}>· {assumption}</small>)}</div>
            </div>
            <div className="simulation-card"><div className="card-heading"><div><p className="eyebrow">TRIP SIMULATOR</p><h3>What if today changes?</h3></div><span className="sim-badge"><span />READY</span></div><p className="intelligence-copy">Throw a small problem at the plan. The recalibrator will protect the best parts of your day.</p><div className="simulation-current"><span className="simulation-pin"><Icon name="sun" size={15} /></span><span><small>UP NEXT</small><strong>{stops.find((stop) => stop.type === 'lunch')?.place || 'Destination'}</strong></span></div><div className="simulation-actions"><button onClick={() => simulateTrip('closed')} disabled={isSimulating}><Icon name="clock" size={14} />Closed</button><button onClick={() => simulateTrip('crowded')} disabled={isSimulating}><Icon name="users" size={14} />Too crowded</button><button onClick={() => simulateTrip('running_late')} disabled={isSimulating}><Icon name="arrowUp" size={14} />Running late</button></div>{simulationResult && <div className={`simulation-result ${simulationResult.action === 'go_to_destination' ? 'direct' : ''}`} role="status"><Icon name={simulationResult.action === 'go_to_destination' ? 'arrow' : 'check'} size={14} /><span>{simulationResult.action === 'go_to_destination' ? 'Going direct' : 'Plan recalibrated'}<small>{simulationResult.message}</small></span></div>}</div>
          </section>

          <footer className="page-footer"><span>Built for exchange students who want a little more from the way there.</span><span><Icon name="sun" size={14} />Good routes, better stories.</span></footer>
        </div>
      </main>
    </div>
  );
}

export default App;
