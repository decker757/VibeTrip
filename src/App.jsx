import { useMemo, useState } from 'react';

const PLANNER_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const navItems = [
  { label: 'Plan a trip', icon: 'compass' },
  { label: 'Explore', icon: 'sparkles' },
  { label: 'Saved trips', icon: 'bookmark', count: '3' },
];

const initialStops = [
  { time: '08:10', title: 'Coffee + stretch', place: 'The Coffee Exchange', detail: 'Providence, RI', type: 'coffee', duration: '25 min' },
  { time: '10:55', title: 'Fuel up', place: 'Shell · Exit 8', detail: 'New Haven, CT', type: 'fuel', duration: '15 min' },
  { time: '12:30', title: 'Lunch with a view', place: 'The Lobster Shack', detail: 'Mystic, CT', type: 'lunch', duration: '55 min' },
  { time: '15:40', title: 'Check-in', place: 'The Hoxton, Williamsburg', detail: 'Brooklyn, NY', type: 'stay', duration: 'overnight' },
];

const initialCandidates = [
  { id: 'demo-coffee', name: 'The Coffee Exchange', category: 'Cafe', address: 'Providence, RI', rating: 4.6, review_count: 825, price_label: '$', detour_minutes: 3, enjoyment_score: 86, crowd_risk: 'low', open_now: true, reason: 'A calm reset with strong reviews and almost no route drift.' },
  { id: 'demo-lunch', name: 'The Lobster Shack', category: 'Restaurant', address: 'Mystic, CT', rating: 4.5, review_count: 1100, price_label: '$$', detour_minutes: 12, enjoyment_score: 88, crowd_risk: 'medium', open_now: true, reason: 'Best balance of a memorable meal, student budget, and route fit.' },
  { id: 'demo-attraction', name: 'Mystic Seaport Museum', category: 'Tourist attraction', address: 'Mystic, CT', rating: 4.7, review_count: 3200, price_label: '$$', detour_minutes: 14, enjoyment_score: 81, crowd_risk: 'high', open_now: true, reason: 'High delight potential, but arrive before the afternoon crowd.' },
  { id: 'demo-fuel', name: 'Shell · Exit 8', category: 'Gas station', address: 'New Haven, CT', rating: 4.1, review_count: 410, price_label: '$', detour_minutes: 2, enjoyment_score: 72, crowd_risk: 'low', open_now: true, reason: 'Low-friction fuel and bathroom stop before the final leg.' },
];

function Icon({ name, size = 18 }) {
  const paths = {
    arrow: <><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>,
    arrowUp: <><path d="m12 19V5" /><path d="m5 12 7-7 7 7" /></>,
    bookmark: <path d="M6 4.75A1.75 1.75 0 0 1 7.75 3h8.5A1.75 1.75 0 0 1 18 4.75V21l-6-3.5L6 21V4.75Z" />,
    calendar: <><rect x="3" y="4.5" width="18" height="17" rx="2" /><path d="M16 2.5v4M8 2.5v4M3 9h18" /></>,
    check: <path d="m5 12 4.2 4.2L19 6.5" />,
    chevron: <path d="m9 18 6-6-6-6" />,
    clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3.5 2" /></>,
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
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.8 1.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5v.2h-2.6v-.2a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1-1.8-1.8.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H6.3v-2.6h.2a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1 1.8-1.8.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.5v-.2H15v.2a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1 1.8 1.8-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.5 1h.2V15h-.2a1.7 1.7 0 0 0-1.5 0Z" /></>,
    sparkles: <><path d="m12 3 1.1 4.2L17 9l-3.9 1.8L12 15l-1.1-4.2L7 9l3.9-1.8L12 3ZM19 14l.6 2.4L22 17l-2.4.6L19 20l-.6-2.4L16 17l2.4-.6L19 14ZM5 15l.7 2.3L8 18l-2.3.7L5 21l-.7-2.3L2 18l2.3-.7L5 15Z" /></>,
    suitcase: <><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2" /></>,
    sun: <><circle cx="12" cy="12" r="3.5" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
    users: <><path d="M16 20v-1.5a3.5 3.5 0 0 0-3.5-3.5h-5A3.5 3.5 0 0 0 4 18.5V20" /><circle cx="10" cy="7.5" r="3.5" /><path d="M16 4.3a3.5 3.5 0 0 1 0 6.7M20 20v-1.5a3.5 3.5 0 0 0-2.5-3.4" /></>,
    wallet: <><path d="M4 6.5A2.5 2.5 0 0 1 6.5 4H19v16H6.5A2.5 2.5 0 0 1 4 17.5v-11Z" /><path d="M4 8h15v4h-3a2 2 0 1 0 0 4h3" /></>,
  };
  return <svg aria-hidden="true" className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

function RouteMap({ candidates = [] }) {
  const markerPositions = [[30, 22], [43, 37], [55, 53], [67, 68]];
  return (
    <div className="map-canvas" aria-label="Map preview of the route from Boston to New York">
      <div className="map-controls">
        <button className="map-button active" aria-label="Map view"><Icon name="map" size={16} /></button>
        <button className="map-button" aria-label="Layers"><Icon name="layers" size={16} /></button>
      </div>
      <div className="map-zoom"><button aria-label="Zoom in"><Icon name="plus" size={16} /></button><button aria-label="Zoom out"><span>−</span></button></div>
      <div className="map-label label-boston">BOSTON</div>
      <div className="map-label label-providence">PROVIDENCE</div>
      <div className="map-label label-newhaven">NEW HAVEN</div>
      <div className="map-label label-nyc">NEW YORK</div>
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
      <div className="map-legend"><span className="legend-route" />VibeTrip route <span className="legend-time">3h 49m</span></div>
    </div>
  );
}

function LocationField({ label, value, onChange, icon }) {
  return (
    <label className="location-field">
      <span className="field-label">{label}</span>
      <span className="field-row"><span className={`location-dot ${icon}`} /> <input aria-label={label} value={value} onChange={(event) => onChange(event.target.value)} /></span>
    </label>
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

function itineraryToStops(itinerary, detours, destination) {
  const detour = detours?.[0];
  const details = {
    coffee: { place: 'Coffee + stretch', detail: 'Along the route', type: 'coffee' },
    fuel: { place: 'Fuel + bathroom', detail: 'On-route station', type: 'fuel' },
    meal: { place: detour?.name || 'Lunch with a view', detail: detour?.city || 'Along the route', type: 'lunch' },
    stay: { place: 'Destination check-in', detail: destination, type: 'stay' },
  };

  return itinerary.map((item) => ({
    time: item.time,
    title: item.title,
    place_id: item.place_id,
    duration: item.duration_min ? `${item.duration_min} min` : 'overnight',
    ...(details[item.kind] || details.coffee),
  }));
}

function candidateToStop(candidate) {
  return {
    time: '12:30',
    title: candidate.name,
    place: candidate.name,
    detail: candidate.address || 'Along the route',
    type: candidate.category?.toLowerCase().includes('cafe') ? 'coffee' : 'lunch',
    duration: '45 min',
    place_id: candidate.id,
  };
}

function App() {
  const [from, setFrom] = useState('Boston, MA');
  const [to, setTo] = useState('New York, NY');
  const [stops, setStops] = useState(initialStops);
  const [activeNav, setActiveNav] = useState('Plan a trip');
  const [activeFilter, setActiveFilter] = useState('Balanced');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isGenerated, setIsGenerated] = useState(false);
  const [message, setMessage] = useState('');
  const [plannerSource, setPlannerSource] = useState('demo');
  const [routeStats, setRouteStats] = useState({ driveMinutes: 229, distanceKm: 348, confidence: 94 });
  const [candidatePlaces, setCandidatePlaces] = useState(initialCandidates);
  const [selectedPlaceId, setSelectedPlaceId] = useState('demo-lunch');
  const [isSimulating, setIsSimulating] = useState(false);
  const [simulationResult, setSimulationResult] = useState(null);

  const routeTitle = useMemo(() => `${from.split(',')[0]} → ${to.split(',')[0]}`, [from, to]);

  async function generateTrip() {
    if (isGenerating) return;
    setIsGenerating(true);
    setMessage('');

    const request = {
      start: from,
      destination: to,
      travellers: 4,
      budget_per_person: 400,
      dates: '2025-09-14/2025-09-16',
      preferences: ['adventurous', 'local-gems', 'slow-mornings', 'student-budget'],
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
      setStops(itineraryToStops(result.itinerary || [], result.detours, result.destination));
      setRouteStats({
        driveMinutes: result.route?.drive_minutes || 229,
        distanceKm: result.route?.distance_km || 348,
        confidence: result.confidence || 94,
      });
      setPlannerSource('api');
      setIsGenerated(true);
      setMessage(result.warning || 'Route ready — places scored by route fit, budget, ratings, and opening hours.');
    } catch {
      // The local preview keeps the MVP usable when FastAPI is not running yet.
      setPlannerSource('demo');
      setCandidatePlaces(initialCandidates);
      setSelectedPlaceId('demo-lunch');
      window.setTimeout(() => {
        setIsGenerated(true);
        setMessage('API unavailable — loaded a local preview so you can keep exploring.');
      }, 350);
    } finally {
      setIsGenerating(false);
    }
  }

  function addStop() {
    setStops((current) => [...current, { time: '17:15', title: 'Sunset option', place: 'DUMBO waterfront', detail: 'Brooklyn, NY', type: 'lunch', duration: '40 min' }]);
    setMessage('Optional sunset stop added to your route.');
  }

  function selectCandidate(candidate) {
    setSelectedPlaceId(candidate.id);
    setStops((current) => current.map((stop) => stop.type === 'lunch' ? candidateToStop(candidate) : stop));
    setMessage(`${candidate.name} is now your preferred detour.`);
  }

  async function simulateTrip(event) {
    if (isSimulating) return;
    setIsSimulating(true);
    setSimulationResult(null);
    const currentStop = stops.find((stop) => stop.type === 'lunch') || stops[2];
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
        body: JSON.stringify({ destination: to, current_stop_id: selectedPlaceId, current_stop_title: currentStop?.title || 'Lunch with a view', event, candidates: candidatePlaces, itinerary }),
      });
      if (!response.ok) throw new Error(`Simulation returned ${response.status}`);
      const result = await response.json();
      setSimulationResult(result);
      setMessage(result.message);
      if (result.replacement) {
        setStops((current) => current.map((stop) => stop.type === 'lunch' ? candidateToStop(result.replacement) : stop));
        setSelectedPlaceId(result.replacement.id);
      } else if (result.action === 'go_to_destination') {
        setStops((current) => current.filter((stop) => stop.type !== 'lunch'));
      }
    } catch {
      const backup = candidatePlaces.find((candidate) => candidate.id !== selectedPlaceId && candidate.open_now && (event !== 'crowded' || candidate.crowd_risk !== 'high'));
      const result = backup
        ? { action: 'replace_stop', replacement: backup, message: `Local simulation: swapped in ${backup.name} as the next best fit.` }
        : { action: 'go_to_destination', message: `Local simulation: continue to ${to}.` };
      setSimulationResult(result);
      setMessage(result.message);
      if (backup) {
        setStops((current) => current.map((stop) => stop.type === 'lunch' ? candidateToStop(backup) : stop));
        setSelectedPlaceId(backup.id);
      } else {
        setStops((current) => current.filter((stop) => stop.type !== 'lunch'));
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

          <section className="planner-card">
            <div className="planner-fields">
              <LocationField label="STARTING FROM" value={from} onChange={setFrom} icon="start" />
              <button className="swap-button" onClick={swapLocations} aria-label="Swap starting point and destination"><Icon name="arrow" size={16} /></button>
              <LocationField label="DESTINATION" value={to} onChange={setTo} icon="end" />
            </div>
            <div className="planner-divider" />
            <div className="planner-options">
              <button className="option-chip"><Icon name="calendar" size={15} /><span><small>DATES</small>14 — 16 SEP 2025</span><Icon name="chevron" size={14} /></button>
              <button className="option-chip"><Icon name="users" size={15} /><span><small>TRAVELLERS</small>4 STUDENTS</span><Icon name="chevron" size={14} /></button>
              <button className="option-chip"><Icon name="wallet" size={15} /><span><small>BUDGET</small>SGD 400 / PERSON</span><Icon name="chevron" size={14} /></button>
              <button className={`generate-button ${isGenerating ? 'loading' : ''}`} onClick={generateTrip} disabled={isGenerating}><span>{isGenerating ? 'Building your route' : isGenerated ? 'Regenerate route' : 'Make my route'}</span>{isGenerating ? <span className="button-loader" /> : <Icon name="arrow" size={17} />}</button>
            </div>
          </section>

          {message && <div className="live-message" role="status"><Icon name="check" size={15} />{message}</div>}

          <section className="route-section">
            <div className="section-heading"><div><p className="eyebrow">YOUR FIRST DRAFT <span>·</span> {plannerSource === 'api' ? 'LANGGRAPH' : 'LOCAL PREVIEW'}</p><h2>{routeTitle}</h2></div><div className="route-meta"><span><Icon name="clock" size={15} />{formatDuration(routeStats.driveMinutes)} drive</span><span><Icon name="map" size={15} />{routeStats.distanceKm} km</span><button className="text-button" onClick={() => setMessage('Route details are ready to connect to your map provider.')}>View details <Icon name="arrow" size={14} /></button></div></div>
            <div className="route-grid">
              <div className="map-card"><RouteMap candidates={candidatePlaces} /><div className="map-footer"><div><span className="map-footer-label">ROUTE CONFIDENCE</span><strong>{routeStats.confidence}% <span>·</span> clear and comfortable</strong></div><span className="route-badge"><Icon name="check" size={13} /> Efficient detour</span></div></div>
              <div className="timeline-card">
                <div className="timeline-top"><div><p className="eyebrow">DAY 01 <span>·</span> SAT 14 SEP</p><h3>Easy pace to {to.split(',')[0]}</h3></div><button className="edit-button" onClick={() => setMessage('Timeline editing is ready for agent handoff.')}><Icon name="edit" size={15} />Edit</button></div>
                <div className="timeline-list">{stops.map((stop, index) => <div className="timeline-item" key={`${stop.title}-${index}`}><div className="timeline-time">{stop.time}</div><div className="timeline-rail"><StopIcon type={stop.type} />{index < stops.length - 1 && <span className="rail-line" />}</div><div className="timeline-copy"><strong>{stop.title}</strong><span>{stop.place} <i>·</i> {stop.detail}</span></div><span className="duration">{stop.duration}</span></div>)}</div>
                <button className="add-stop" onClick={addStop}><Icon name="plus" size={15} />Add a stop</button>
              </div>
            </div>
          </section>

          <section className="intelligence-grid">
            <div className="suggestions-card">
              <div className="card-heading"><div><p className="eyebrow">ALONG YOUR ROUTE</p><h3>Places worth the turn.</h3></div><span className="source-badge"><Icon name="sparkles" size={12} />{plannerSource === 'api' ? 'LIVE PLACES' : 'DEMO DATA'}</span></div>
              <p className="intelligence-copy">The detour reviewer weighs reviews, price, opening hours, estimated crowd risk, and time lost.</p>
              <div className="candidate-list">{candidatePlaces.slice(0, 4).map((candidate) => <div className={`candidate-row ${selectedPlaceId === candidate.id ? 'selected' : ''}`} key={candidate.id}><div className="candidate-icon"><Icon name={candidate.category?.toLowerCase().includes('restaurant') ? 'sun' : candidate.category?.toLowerCase().includes('gas') ? 'fuel' : 'sparkles'} size={15} /></div><div className="candidate-copy"><strong>{candidate.name}</strong><span>{candidate.category} <i>·</i> {candidate.address}</span><small><span className="rating-star">★</span> {Number(candidate.rating || 0).toFixed(1)} ({Number(candidate.review_count || 0).toLocaleString()}) <i>·</i> {candidate.detour_minutes} min detour</small></div><div className="candidate-score"><strong>{candidate.enjoyment_score}</strong><small>enjoyment</small></div><button className="candidate-use" onClick={() => selectCandidate(candidate)}>{selectedPlaceId === candidate.id ? 'Selected' : 'Use'}</button></div>)}</div>
            </div>
            <div className="simulation-card"><div className="card-heading"><div><p className="eyebrow">TRIP SIMULATOR</p><h3>What if today changes?</h3></div><span className="sim-badge"><span />READY</span></div><p className="intelligence-copy">Throw a small problem at the plan. The recalibrator will protect the best parts of your day.</p><div className="simulation-current"><span className="simulation-pin"><Icon name="sun" size={15} /></span><span><small>UP NEXT</small><strong>{stops.find((stop) => stop.type === 'lunch')?.place || 'Destination'}</strong></span></div><div className="simulation-actions"><button onClick={() => simulateTrip('closed')} disabled={isSimulating}><Icon name="clock" size={14} />Closed</button><button onClick={() => simulateTrip('crowded')} disabled={isSimulating}><Icon name="users" size={14} />Too crowded</button><button onClick={() => simulateTrip('running_late')} disabled={isSimulating}><Icon name="arrowUp" size={14} />Running late</button></div>{simulationResult && <div className={`simulation-result ${simulationResult.action === 'go_to_destination' ? 'direct' : ''}`} role="status"><Icon name={simulationResult.action === 'go_to_destination' ? 'arrow' : 'check'} size={14} /><span>{simulationResult.action === 'go_to_destination' ? 'Going direct' : 'Plan recalibrated'}<small>{simulationResult.message}</small></span></div>}</div>
          </section>

          <section className="bottom-grid">
            <div className="agent-card"><div className="card-heading"><div><p className="eyebrow">HOW IT CAME TOGETHER</p><h3>Your route, reasoned out.</h3></div><span className="live-pill"><span />LIVE</span></div><p className="agent-description">VibeTrip’s agents are checking the route for good detours, realistic energy levels, and places that feel like your kind of day.</p><div className="agent-progress"><div className={`agent-step ${isGenerated ? 'done' : 'active'}`}><span className="agent-step-icon">{isGenerated ? <Icon name="check" size={13} /> : <span className="pulse-dot" />}</span><span><strong>Route scout</strong><small>{isGenerated ? 'Fastest route found' : 'Finding the cleanest route'}</small></span></div><div className="agent-connector" /><div className="agent-step done"><span className="agent-step-icon"><Icon name="check" size={13} /></span><span><strong>Vibe matcher</strong><small>Adventure level: curious</small></span></div><div className="agent-connector" /><div className={`agent-step ${isGenerated ? 'done' : ''}`}><span className="agent-step-icon">{isGenerated ? <Icon name="check" size={13} /> : <span className="step-number">3</span>}</span><span><strong>Day builder</strong><small>{isGenerated ? 'Breathing room added' : 'Waiting on route'}</small></span></div></div></div>
            <div className="profile-card"><div className="card-heading"><div><p className="eyebrow">TRAVEL PROFILE</p><h3>Curious, not rushed.</h3></div><button className="edit-link" onClick={() => setMessage('Travel profile editing is coming next.')}>Edit profile <Icon name="arrow" size={13} /></button></div><div className="profile-tags"><span><Icon name="sparkles" size={14} />Local gems</span><span><Icon name="clock" size={14} />Slow mornings</span><span><Icon name="wallet" size={14} />Student budget</span></div><div className="profile-meter"><div className="meter-labels"><span>ADVENTUROUS</span><span>LAID BACK</span></div><div className="meter-track"><span /></div></div></div>
          </section>

          <footer className="page-footer"><span>Built for exchange students who want a little more from the way there.</span><span><Icon name="sun" size={14} />Good routes, better stories.</span></footer>
        </div>
      </main>
    </div>
  );
}

export default App;
