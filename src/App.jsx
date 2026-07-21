import { useEffect, useMemo, useRef, useState } from 'react';
import PlannerPage from './components/PlannerPage';
import Icon from './components/Icon';
import AuthView from './components/AuthView';
import ProfileOnboarding from './components/ProfileOnboarding';
import { ExploreView, SavedTripsView } from './components/TripCollections';
import ProfileView from './components/ProfileView';
import { addMinutesToTime, buildClientCostBreakdown, buildGoogleMapsUrl, candidateToStop, getInitials, itineraryToStops } from './app/formatters';
import { estimateTripEndDate, getLocalTimeISO, getLocalTodayISO } from './app/dateUtils';
import { MAX_TRIP_MEDIA } from './app/media';
import { defaultCostBreakdown, exploreFallbackTrips, initialCandidates, initialStops, navItems, PLANNER_API_URL, profileOptions, routeModeOptions, tripProfileOptions } from './app/plannerData';

function apiFetch(input, options = {}) {
  return fetch(input, { ...options, credentials: 'include' });
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error || new Error('Unable to read this media file.'));
    reader.readAsDataURL(file);
  });
}

function savedTripsKey(ownerId) {
  return `vibetrip.savedTrips.${ownerId || 'demo-user'}`;
}

function normalizeSavedTrip(trip) {
  if (!trip || !Array.isArray(trip.preferences)) return trip;
  return { ...trip, preferences: trip.preferences.filter((preference) => preference !== 'student-budget') };
}

function normalizeSavedTrips(trips) {
  return Array.isArray(trips) ? trips.map(normalizeSavedTrip) : [];
}

function profileDefaultsKey(ownerId) {
  return `vibetrip.profileDefaults.${ownerId || 'demo-user'}`;
}

function onboardingKey(ownerId) {
  return `vibetrip.onboardingComplete.${ownerId || 'demo-user'}`;
}

function readProfileDefaults(ownerId) {
  try {
    const saved = JSON.parse(window.localStorage.getItem(profileDefaultsKey(ownerId)) || 'null');
    const savedPreferences = Array.isArray(saved?.preferences) ? saved.preferences : ['adventurous', 'local-gems', 'slow-mornings'];
    return {
      preferences: savedPreferences.filter((preference) => preference !== 'student-budget'),
      adventureLevel: Number.isFinite(Number(saved?.adventure_level)) ? Number(saved.adventure_level) : 70,
    };
  } catch {
    return { preferences: ['adventurous', 'local-gems', 'slow-mornings'], adventureLevel: 70 };
  }
}

const navPaths = {
  'Plan a trip': '/plan',
  Explore: '/explore',
  'Saved trips': '/saved-trips',
  'Travel profile': '/profile',
};

function navFromPath(pathname) {
  return Object.entries(navPaths).find(([, path]) => pathname === path)?.[0] || 'Plan a trip';
}

function App() {
  const [from, setFrom] = useState('Boston, MA');
  const [to, setTo] = useState('New York, NY');
  const [fromLocation, setFromLocation] = useState(null);
  const [toLocation, setToLocation] = useState(null);
  const [stops, setStops] = useState(initialStops);
  const [activeNav, setActiveNav] = useState(() => navFromPath(window.location.pathname));
  const [routeMode, setRouteMode] = useState('balanced');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isRerouting, setIsRerouting] = useState(false);
  const [isGenerated, setIsGenerated] = useState(false);
  const [message, setMessage] = useState('');
  const [plannerSource, setPlannerSource] = useState('demo');
  const [recommendationSource, setRecommendationSource] = useState('deterministic');
  const [contextSummary, setContextSummary] = useState(null);
  const [routeStats, setRouteStats] = useState({ driveMinutes: 229, distanceKm: 348, confidence: 94 });
  const [route, setRoute] = useState({});
  const [startDate, setStartDate] = useState(() => getLocalTodayISO());
  const [endDate, setEndDate] = useState(() => getLocalTodayISO());
  const [startTime, setStartTime] = useState(() => getLocalTimeISO());
  const [endTime, setEndTime] = useState('18:00');
  const [travellers, setTravellers] = useState(4);
  const [budgetPerPerson, setBudgetPerPerson] = useState(400);
  const [adventureLevel, setAdventureLevel] = useState(70);
  const [preferences, setPreferences] = useState(['adventurous', 'local-gems', 'slow-mornings']);
  const [profileAdventureLevel, setProfileAdventureLevel] = useState(() => readProfileDefaults('demo-user').adventureLevel);
  const [profilePreferences, setProfilePreferences] = useState(() => readProfileDefaults('demo-user').preferences);
  const [candidatePlaces, setCandidatePlaces] = useState(initialCandidates);
  const [selectedPlaceId, setSelectedPlaceId] = useState('demo-lunch');
  const [costBreakdown, setCostBreakdown] = useState(() => buildClientCostBreakdown({ distance_km: 348 }, initialCandidates[1], 4));
  const [editingStopIndex, setEditingStopIndex] = useState(null);
  const [focusedStopIndex, setFocusedStopIndex] = useState(null);
  const [isManagingStops, setIsManagingStops] = useState(false);
  const [placeQuery, setPlaceQuery] = useState('');
  const [placeSearchResults, setPlaceSearchResults] = useState([]);
  const [placeSearchHint, setPlaceSearchHint] = useState('');
  const [hasSearchedPlaces, setHasSearchedPlaces] = useState(false);
  const [isSearchingPlaces, setIsSearchingPlaces] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simulationResult, setSimulationResult] = useState(null);
  const [savedTrips, setSavedTrips] = useState(() => {
    try {
      return normalizeSavedTrips(JSON.parse(window.localStorage.getItem(savedTripsKey('demo-user')) || '[]'));
    } catch {
      return [];
    }
  });
  const [isLoadingCollection, setIsLoadingCollection] = useState(false);
  const [isSavingTrip, setIsSavingTrip] = useState(false);
  const [userProfile, setUserProfile] = useState(() => {
    try {
      return JSON.parse(window.localStorage.getItem('vibetrip.userProfile') || '{"name":"VibeTrip traveller","home":"Singapore"}');
    } catch {
      return { name: 'VibeTrip traveller', home: 'Singapore' };
    }
  });
  const [authUser, setAuthUser] = useState(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [isOnboarding, setIsOnboarding] = useState(false);
  const [isAccountMenuOpen, setIsAccountMenuOpen] = useState(false);
  const hasAutoGeneratedRef = useRef(false);
  const mapControllerRef = useRef(null);
  const activeTripIdRef = useRef(null);

  async function recordAgentEvent(eventType, data = {}, tripId = null) {
    if (!authUser) return;
    try {
      await apiFetch(`${PLANNER_API_URL}/profiles/events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event_type: eventType, trip_id: tripId || activeTripIdRef.current || null, data }),
      });
    } catch {
      // Feedback is helpful context, but it must never block route editing.
    }
  }

  useEffect(() => {
    let isActive = true;
    apiFetch(`${PLANNER_API_URL}/auth/me`)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('Not authenticated')))
      .then((result) => {
        if (!isActive) return;
        establishAuthenticatedSession(result.user);
      })
      .catch(() => {})
      .finally(() => { if (isActive) setIsAuthLoading(false); });
    return () => { isActive = false; };
  }, []);

  useEffect(() => {
    if (!isAuthLoading && !authUser && window.location.pathname !== '/login') {
      window.history.replaceState({}, '', '/login');
    }
  }, [authUser, isAuthLoading]);

  useEffect(() => {
    const handlePopState = () => setActiveNav(navFromPath(window.location.pathname));
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    if (isAuthLoading || !authUser) return;
    window.localStorage.setItem(profileDefaultsKey(authUser.id), JSON.stringify({ preferences: profilePreferences, adventure_level: profileAdventureLevel }));
  }, [authUser, isAuthLoading, profilePreferences, profileAdventureLevel]);

  function navigateTo(nextNav, { replace = false } = {}) {
    const nextPath = navPaths[nextNav] || navPaths['Plan a trip'];
    window.history[replace ? 'replaceState' : 'pushState']({}, '', nextPath);
    setActiveNav(nextNav);
    setIsAccountMenuOpen(false);
  }

  function establishAuthenticatedSession(user) {
    setAuthUser(user);
    setUserProfile({ name: user.display_name, home: user.home_base });
    const defaults = readProfileDefaults(user.id);
    setProfilePreferences(defaults.preferences);
    setProfileAdventureLevel(defaults.adventureLevel);
    syncTripPreferencesFromProfile(defaults);
    try {
      setSavedTrips(JSON.parse(window.localStorage.getItem(savedTripsKey(user.id)) || '[]'));
    } catch {
      setSavedTrips([]);
    }
    const needsOnboarding = window.localStorage.getItem(onboardingKey(user.id)) !== 'true';
    setIsOnboarding(needsOnboarding);
    if (needsOnboarding) {
      window.history.replaceState({}, '', '/onboarding');
      setActiveNav('Plan a trip');
    } else if (window.location.pathname === '/login' || window.location.pathname === '/onboarding' || window.location.pathname === '/') {
      navigateTo('Plan a trip', { replace: true });
    }
  }

  const routeTitle = useMemo(() => `${from.split(',')[0]} → ${to.split(',')[0]}`, [from, to]);
  const defaultReplacementIndex = Math.max(0, stops.findIndex((stop) => stop.type === 'lunch'));
  const replacementStopIndex = editingStopIndex ?? focusedStopIndex ?? defaultReplacementIndex;
  const displayedCandidates = useMemo(() => candidatePlaces.slice(0, routeMode === 'fastest' ? 4 : 6), [candidatePlaces, routeMode]);
  const destinationCandidates = useMemo(() => candidatePlaces.filter((candidate) => candidate.recommendation_scope === 'destination').slice(0, 4), [candidatePlaces]);
  const mapCandidates = useMemo(() => {
    const visibleIds = new Set(displayedCandidates.map((candidate) => candidate.id));
    const waypointIds = new Set([
      ...stops.map((stop) => stop.place_id).filter(Boolean),
      ...(route.routed_waypoint_ids || []),
    ]);
    return candidatePlaces.filter((candidate) => visibleIds.has(candidate.id) || waypointIds.has(candidate.id));
  }, [candidatePlaces, displayedCandidates, route.routed_waypoint_ids, stops]);
  const googleMapsUrl = useMemo(() => buildGoogleMapsUrl(from, to, stops), [from, to, stops]);
  const profileSummary = profileAdventureLevel >= 70 ? 'Curious, not rushed.' : profileAdventureLevel <= 35 ? 'Easygoing, well paced.' : 'Balanced, open to detours.';
  const profileBalance = profileAdventureLevel >= 70 ? 'More adventurous' : profileAdventureLevel <= 35 ? 'More laid back' : 'Balanced pace';
  const tripProfileSummary = adventureLevel >= 70 ? 'Curious, not rushed.' : adventureLevel <= 35 ? 'Easygoing, well paced.' : 'Balanced, open to detours.';
  const tripProfileBalance = adventureLevel >= 70 ? 'More adventurous' : adventureLevel <= 35 ? 'More laid back' : 'Balanced pace';

  async function generateTrip(overrides = {}) {
    if (isGenerating) return;
    setIsGenerating(true);
    setMessage('');

    const requestFrom = overrides.from ?? from;
    const requestTo = overrides.to ?? to;
    const requestStartDate = overrides.startDate ?? startDate;
    // The planner derives arrival day from route duration. Keep the date in
    // the request for backwards-compatible saved-trip/API payloads.
    const requestEndDate = overrides.endDate ?? requestStartDate;
    const requestStartTime = overrides.startTime ?? startTime;
    const requestEndTime = overrides.endTime ?? endTime;
    const requestTravellers = overrides.travellers ?? travellers;
    const requestBudgetPerPerson = overrides.budgetPerPerson ?? budgetPerPerson;
    const requestPreferences = (overrides.preferences ?? preferences).filter((preference) => preference !== 'student-budget');
    const requestAdventureLevel = overrides.adventureLevel ?? adventureLevel;
    const requestRouteMode = overrides.routeMode ?? routeMode;

    if (!requestFrom.trim() || !requestTo.trim()) {
      setMessage('Add both a starting city and destination before planning.');
      setIsGenerating(false);
      return;
    }
    const request = {
      start: requestFrom,
      destination: requestTo,
      travellers: requestTravellers,
      budget_per_person: requestBudgetPerPerson,
      dates: `${requestStartDate}/${requestEndDate}`,
      start_date: requestStartDate,
      end_date: requestEndDate,
      start_time: requestStartTime,
      end_time: requestEndTime,
      preferences: requestPreferences,
      adventure_level: requestAdventureLevel,
      route_mode: requestRouteMode,
      profile: {
        name: userProfile.name || 'VibeTrip traveller',
        home_base: userProfile.home || 'Singapore',
        exchange_student: true,
      },
    };

    try {
      const response = await apiFetch(`${PLANNER_API_URL}/trips/plan`, {
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
      setEndDate(estimateTripEndDate(requestStartDate, result.route, result.itinerary || []));
      setCostBreakdown(result.cost_breakdown || buildClientCostBreakdown(result.route, candidates[0], requestTravellers));
      setPlannerSource('api');
      setRecommendationSource(result.recommendation_source || 'deterministic');
      setContextSummary(result.context_summary || result.profile_context?.summary || null);
      setIsGenerated(true);
      const contextMessage = result.context_summary?.label ? ` ${result.context_summary.label}.` : '';
      setMessage(result.warning || `${routeModeOptions.find((option) => option.id === requestRouteMode)?.label} route ready — ${result.recommendation_source === 'llm' ? 'the LLM reviewer ranked the feasible candidates' : 'deterministic scoring ranked the feasible candidates'}.${contextMessage}`);
    } catch {
      // The local preview keeps the MVP usable when FastAPI is not running yet.
      setPlannerSource('demo');
      setRecommendationSource('deterministic');
      setContextSummary(null);
      setCandidatePlaces(initialCandidates);
      setSelectedPlaceId('demo-lunch');
      setRoute({});
      setEndDate(requestStartDate);
      setCostBreakdown(buildClientCostBreakdown({ distance_km: 348 }, initialCandidates[1], requestTravellers));
      window.setTimeout(() => {
        setIsGenerated(true);
        setMessage('API unavailable — loaded a local preview so you can keep exploring.');
      }, 350);
    } finally {
      setIsGenerating(false);
    }
  }

  useEffect(() => {
    if (activeNav !== 'Plan a trip') return;
    if (hasAutoGeneratedRef.current) return;
    hasAutoGeneratedRef.current = true;
    generateTrip();
  }, [activeNav]);

  async function rerouteDraft(nextStops, successMessage) {
    if (isRerouting) return;
    setIsRerouting(true);
    try {
      const response = await apiFetch(`${PLANNER_API_URL}/trips/reroute`, {
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
    const previousStop = stops[targetIndex];
    const nextStops = stops.map((stop, index) => index === targetIndex ? candidateToStop(candidate, stop.time) : stop);
    setSelectedPlaceId(candidate.id);
    setStops(nextStops);
    setFocusedStopIndex(targetIndex);
    setEditingStopIndex(null);
    setIsManagingStops(true);
    setCostBreakdown(buildClientCostBreakdown(route, candidate, travellers));
    void recordAgentEvent('stop_replaced', {
      old_place: previousStop?.title || 'selected stop',
      new_place: candidate.name,
      reason: placeQuery || 'user selected a route alternative',
      route_progress_km: candidate.route_progress_km,
    });
    void rerouteDraft(nextStops, `${candidate.name} selected and the route was recalculated through it.`);
  }

  function focusCandidate(candidate) {
    const timelineIndex = stops.findIndex((stop) => stop.place_id === candidate.id);
    if (timelineIndex >= 0) {
      focusTimelineStop(stops[timelineIndex], timelineIndex);
      return;
    }
    const focused = mapControllerRef.current?.focusStop(candidateToStop(candidate));
    setMessage(focused ? `${candidate.name} focused on the map. Choose “Use here” to add it to the selected stop.` : `${candidate.name} selected. Choose “Use here” to add it to the selected stop.`);
  }

  function addDestinationCandidate(candidate) {
    const existingIndex = stops.findIndex((stop) => stop.place_id === candidate.id);
    if (existingIndex >= 0) {
      setFocusedStopIndex(existingIndex);
      setMessage(`${candidate.name} is already in your trip.`);
      return;
    }
    const destinationIndex = stops.findIndex((stop) => stop.type === 'stay');
    const insertionIndex = destinationIndex >= 0 ? destinationIndex : stops.length;
    const previousStop = stops[insertionIndex - 1] || stops[stops.length - 1];
    const time = previousStop?.time ? addMinutesToTime(previousStop.time, (previousStop.duration_minutes || 45) + 30) : startTime;
    const nextStop = candidateToStop(candidate, time);
    const nextStops = [...stops.slice(0, insertionIndex), nextStop, ...stops.slice(insertionIndex)];
    setCandidatePlaces((current) => current.map((item) => item.id === candidate.id ? { ...item, recommendation_scope: 'along_route' } : item));
    setSelectedPlaceId(candidate.id);
    setStops(nextStops);
    setFocusedStopIndex(insertionIndex);
    setCostBreakdown(buildClientCostBreakdown(route, candidate, travellers));
    void recordAgentEvent('destination_added', {
      new_place: candidate.name,
      reason: 'user added an optional destination suggestion',
      route_progress_km: candidate.route_progress_km,
    });
    void rerouteDraft(nextStops, `${candidate.name} added before check-in and the route was recalculated through it.`);
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
    void recordAgentEvent('stop_removed', { old_place: removed?.title || 'selected stop', reason: 'user removed a planned stop' });
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
    void recordAgentEvent('chatbot_search', { query, target_stop: stops[replacementStopIndex]?.title || 'selected stop' });
    const candidateForStop = (stop) => candidatePlaces.find((candidate) => candidate.id === stop?.place_id);
    const progressForStop = (stop) => {
      const progress = stop?.route_progress_km ?? candidateForStop(stop)?.route_progress_km;
      return Number.isFinite(Number(progress)) ? Number(progress) : null;
    };
    const previousStop = [...stops.slice(0, replacementStopIndex)].reverse().find((stop) => stop.type !== 'stay');
    const currentStop = stops[replacementStopIndex];
    const nextStop = stops.slice(replacementStopIndex + 1).find((stop) => stop.type !== 'stay');
    const previousProgress = progressForStop(previousStop);
    const currentProgress = progressForStop(currentStop);
    const nextProgress = progressForStop(nextStop);
    const routeDistance = Number(route.distance_km || routeStats.distanceKm || 348);
    // A stop's route progress can be missing or stale after a saved trip is
    // reopened. Do not let a malformed checkpoint collapse the search window
    // to zero. When replacing the first physical stop, the origin is the
    // lower bound so a user can move it closer to Singapore/Johor and let the
    // next checkpoint be recalculated downstream. Later stops still stay
    // after their previous checkpoint.
    const hasValidPreviousProgress = previousProgress != null && (currentProgress == null || previousProgress < currentProgress);
    const hasValidNextProgress = nextProgress != null && (currentProgress == null || nextProgress > currentProgress);
    const segmentStartProgress = hasValidPreviousProgress
      ? previousProgress
      : currentProgress == null
        ? null
        : previousStop
          ? Math.max(0, currentProgress - 90)
          : 0;
    const fallbackSegmentEnd = currentProgress == null ? null : Math.min(routeDistance, currentProgress + 90);
    const segmentEndProgress = hasValidNextProgress ? nextProgress : fallbackSegmentEnd;
    const isInReplacementSegment = (candidate) => {
      if (segmentStartProgress == null && segmentEndProgress == null) return true;
      const progress = Number(candidate.route_progress_km);
      return Number.isFinite(progress) && progress >= (segmentStartProgress ?? 0) && progress < (segmentEndProgress ?? routeDistance);
    };
    setIsSearchingPlaces(true);
    setPlaceSearchResults([]);
    setPlaceSearchHint('');
    setHasSearchedPlaces(false);
    try {
      const response = await apiFetch(`${PLANNER_API_URL}/trips/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start: from, destination: to, query, budget_per_person: budgetPerPerson, crowd_tolerance: preferences.includes('student-budget') ? 'low' : 'medium', route_mode: routeMode, segment_start_progress_km: segmentStartProgress, segment_end_progress_km: segmentEndProgress, target_progress_km: currentProgress, selected_stop_title: currentStop?.title || '', previous_stop_title: previousStop?.title || '', next_stop_title: nextStop?.title || '' }),
      });
      if (!response.ok) throw new Error(`Search returned ${response.status}`);
      const result = await response.json();
      const contextualResults = (result.candidate_places || []).filter(isInReplacementSegment);
      const parsedIntent = result.parsed_intent || {};
      const locationHint = parsedIntent.location_hint;
      const readableLocation = locationHint ? locationHint.replace(/\b\w/g, (letter) => letter.toUpperCase()) : '';
      const routeHint = previousStop
        ? `Replacement candidates stay between ${previousStop.title} and ${nextStop?.title || to}, so the route stays in order.`
        : `The first stop can move anywhere before ${nextStop?.title || to}; choosing one recalculates the route through it and onward.`;
      const searchHint = locationHint
        ? `Searching for ${parsedIntent.category || 'a place'} near ${readableLocation}. ${routeHint}`
        : routeHint;
      setPlaceSearchHint(result.warning && (result.candidate_places || []).length === 0
        ? `${result.warning} ${searchHint}`
        : searchHint);
      setPlaceSearchResults(contextualResults);
      setHasSearchedPlaces(true);
      setCandidatePlaces((current) => [...contextualResults, ...current.filter((candidate) => !contextualResults.some((match) => match.id === candidate.id))]);
      if (contextualResults.length > 0) {
        setMessage(result.warning || `Found ${contextualResults.length} matches on the ${currentStop?.title || 'selected'} leg for “${query}”.`);
      } else if ((result.candidate_places || []).length > 0) {
        setMessage('Places were found elsewhere on the route, but none fit this selected leg. Choose another stop to replace or broaden the request.');
      } else {
        setMessage(result.warning || 'No suitable places fit this selected leg. Choose another stop to replace or try a more specific request, such as “Chinese restaurant”.');
      }
    } catch {
      const terms = query.toLowerCase().split(/\s+/).filter((term) => term.length > 2);
      const cuisine = ['chinese', 'japanese', 'korean', 'thai', 'indian', 'malay', 'vietnamese', 'mexican', 'italian', 'mediterranean'].find((term) => terms.includes(term));
      const localMatches = candidatePlaces.filter((candidate) => isInReplacementSegment(candidate) && (() => {
        const haystack = `${candidate.name} ${candidate.category} ${candidate.reason}`.toLowerCase();
        return cuisine ? haystack.includes(cuisine) : terms.some((term) => haystack.includes(term));
      })());
      setPlaceSearchResults(localMatches);
      setHasSearchedPlaces(true);
      setMessage(localMatches.length ? 'Showing local route matches while the search service is unavailable.' : 'The route search is unavailable. Try a broader description.');
    } finally {
      setIsSearchingPlaces(false);
    }
  }

  function toggleTripPreference(preference) {
    setPreferences((current) => current.includes(preference) ? current.filter((item) => item !== preference) : [...current, preference]);
  }

  function toggleProfilePreference(preference) {
    setProfilePreferences((current) => current.includes(preference) ? current.filter((item) => item !== preference) : [...current, preference]);
  }

  function updateAdventureLevel(event) {
    const nextLevel = Number(event.target.value);
    setAdventureLevel(nextLevel);
  }

  function syncTripPreferencesFromProfile(defaults) {
    setPreferences((defaults.preferences || []).filter((preference) => preference !== 'student-budget'));
    setAdventureLevel(defaults.adventureLevel);
  }

  function updateProfileAdventureLevel(event) {
    setProfileAdventureLevel(Number(event.target.value));
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
    void recordAgentEvent('simulation_feedback', {
      reason: event,
      current_stop: currentStop?.title || 'selected stop',
    });
    const itinerary = stops.map((stop) => ({
      time: stop.time,
      title: stop.title,
      kind: stop.type === 'lunch' ? 'meal' : stop.type,
      duration_min: Number.parseInt(stop.duration, 10) || 0,
      place_id: stop.place_id,
    }));
    try {
      const response = await apiFetch(`${PLANNER_API_URL}/trips/simulate`, {
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
    setFromLocation(toLocation);
    setToLocation(fromLocation);
    setMessage('Direction swapped.');
  }

  function updateFrom(value, location = null) {
    setFrom(value);
    setFromLocation(location);
  }

  function updateTo(value, location = null) {
    setTo(value);
    setToLocation(location);
  }

  function focusTimelineStop(stop, index) {
    setFocusedStopIndex(index);
    const focused = mapControllerRef.current?.focusStop(stop);
    const mapCard = document.querySelector('.map-card');
    if (mapCard && (mapCard.getBoundingClientRect().top < 0 || mapCard.getBoundingClientRect().bottom > window.innerHeight)) {
      mapCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    const timelineItem = document.querySelector(`.timeline-item[data-stop-index="${index}"]`);
    if (timelineItem && (timelineItem.getBoundingClientRect().top < 0 || timelineItem.getBoundingClientRect().bottom > window.innerHeight)) {
      timelineItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    setMessage(focused ? `${stop.title} focused on the map.` : `${stop.title} selected. Generate a live route to focus it on the map.`);
  }

  async function loadSavedTrips() {
    setIsLoadingCollection(true);
    try {
      const response = await apiFetch(`${PLANNER_API_URL}/trips/saved`);
      if (!response.ok) throw new Error(`Saved trips returned ${response.status}`);
      const result = await response.json();
      const localTrips = normalizeSavedTrips(JSON.parse(window.localStorage.getItem(savedTripsKey(authUser?.id)) || '[]'));
      const mergedTrips = normalizeSavedTrips([...(result.trips || []), ...localTrips]).filter((trip, index, trips) => trips.findIndex((item) => item.id === trip.id) === index);
      setSavedTrips(mergedTrips);
    } catch {
      // Keep saved drafts usable in the local preview when FastAPI is offline.
      try {
        setSavedTrips(normalizeSavedTrips(JSON.parse(window.localStorage.getItem(savedTripsKey(authUser?.id)) || '[]')));
      } catch {
        setSavedTrips([]);
      }
    } finally {
      setIsLoadingCollection(false);
    }
  }

  async function loadExploreTrips() {
    setIsLoadingCollection(true);
    try {
      const preferencesQuery = encodeURIComponent(profilePreferences.join(','));
      const response = await apiFetch(`${PLANNER_API_URL}/trips/explore?preferences=${preferencesQuery}&adventure_level=${profileAdventureLevel}&limit=50`);
      if (!response.ok) throw new Error(`Explore returned ${response.status}`);
      const result = await response.json();
      const remoteTrips = result.trips || [];
      const fallbackByTitle = new Map(exploreFallbackTrips.map((trip) => [trip.title, trip]));
      const mergedTrips = [...remoteTrips, ...exploreFallbackTrips]
        .map((trip) => {
          const fallback = fallbackByTitle.get(trip.title);
          return {
            ...trip,
            cover_image: trip.cover_image || fallback?.cover_image,
            cover_image_fallback: trip.cover_image_fallback || fallback?.cover_image_fallback,
            // A published trip with no uploaded media can still use the seeded
            // community memories for the same built-in route idea.
            media: trip.media?.length ? trip.media : fallback?.media || [],
          };
        })
        .filter((trip, index, trips) => trips.findIndex((item) => item.id === trip.id || item.title === trip.title) === index);
      setExploreTrips(mergedTrips.length ? mergedTrips : exploreFallbackTrips);
    } catch {
      setExploreTrips(exploreFallbackTrips);
    } finally {
      setIsLoadingCollection(false);
    }
  }

  async function saveCurrentTrip() {
    if (isSavingTrip || !isGenerated) return;
    setIsSavingTrip(true);
    const payload = {
      ...(activeTripIdRef.current ? { id: activeTripIdRef.current } : {}),
      owner_id: authUser?.id || 'demo-user',
      title: `${from.split(',')[0]} to ${to.split(',')[0]} · ${routeModeOptions.find((option) => option.id === routeMode)?.label || 'Balanced'}`,
      start: from,
      destination: to,
      route_mode: routeMode,
      adventure_level: adventureLevel,
      budget_per_person: budgetPerPerson,
      travellers,
      start_date: startDate,
      end_date: endDate,
      start_time: startTime,
      end_time: endTime,
      preferences,
      route,
      itinerary: stops,
      candidate_places: candidatePlaces,
      cost_breakdown: costBreakdown,
      media: [],
      post_caption: '',
      is_public: false,
      is_completed: false,
    };
    try {
      const response = await apiFetch(`${PLANNER_API_URL}/trips/save`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (!response.ok) throw new Error(`Save returned ${response.status}`);
      const result = await response.json();
      activeTripIdRef.current = result.trip.id;
      setSavedTrips((current) => {
        const nextTrips = [result.trip, ...current.filter((trip) => trip.id !== result.trip.id)];
        window.localStorage.setItem(savedTripsKey(authUser?.id), JSON.stringify(nextTrips));
        return nextTrips;
      });
      setMessage('Trip saved to your library.');
    } catch {
      const localTrip = { ...payload, id: payload.id || `local-${Date.now()}`, author_name: 'You · Singapore', created_at: new Date().toISOString() };
      activeTripIdRef.current = localTrip.id;
      const nextTrips = [localTrip, ...savedTrips].slice(0, 20);
      setSavedTrips(nextTrips);
      window.localStorage.setItem(savedTripsKey(authUser?.id), JSON.stringify(nextTrips));
      setMessage('Trip saved locally. Start FastAPI to sync it to Postgres.');
    } finally {
      setIsSavingTrip(false);
    }
  }

  async function completeTrip(trip) {
    if (trip.is_completed) return;
    try {
      const response = await apiFetch(`${PLANNER_API_URL}/trips/saved/${encodeURIComponent(trip.id)}/complete`, { method: 'POST' });
      if (!response.ok) throw new Error(`Complete returned ${response.status}`);
      const result = await response.json();
      setSavedTrips((current) => {
        const nextTrips = current.map((item) => item.id === trip.id ? result.trip : item);
        window.localStorage.setItem(savedTripsKey(authUser?.id), JSON.stringify(nextTrips));
        return nextTrips;
      });
    } catch {
      const completedTrip = { ...trip, is_completed: true, updated_at: new Date().toISOString() };
      const nextTrips = savedTrips.map((item) => item.id === trip.id ? completedTrip : item);
      setSavedTrips(nextTrips);
      window.localStorage.setItem(savedTripsKey(authUser?.id), JSON.stringify(nextTrips));
    }
    setMessage('Trip marked completed. It is ready for the Explore feed once published.');
  }

  async function uploadTripMedia(trip, files, replacementMediaId = null) {
    const selectedFiles = Array.from(files || []).slice(0, replacementMediaId ? 1 : Math.max(0, MAX_TRIP_MEDIA - (trip.media || []).length));
    if (!selectedFiles.length) {
      setMessage(replacementMediaId ? 'Choose a file to replace this memory.' : `This trip already has the maximum of ${MAX_TRIP_MEDIA} memories.`);
      return;
    }
    if (selectedFiles.some((file) => file.size > 20 * 1024 * 1024)) {
      setMessage('Each media file must be 20 MB or smaller.');
      return;
    }
    let latestTrip = trip;
    let uploadedCount = 0;
    try {
      for (const file of selectedFiles) {
        const formData = new FormData();
        formData.append('file', file);
        const mediaPath = replacementMediaId
          ? `${PLANNER_API_URL}/trips/saved/${encodeURIComponent(trip.id)}/media/${encodeURIComponent(replacementMediaId)}`
          : `${PLANNER_API_URL}/trips/saved/${encodeURIComponent(trip.id)}/media`;
        const response = await apiFetch(mediaPath, { method: replacementMediaId ? 'PUT' : 'POST', body: formData });
        if (!response.ok) {
          const error = await response.json().catch(() => ({}));
          throw new Error(error.detail || `Media upload returned ${response.status}`);
        }
        const result = await response.json();
        const localPreviewUrl = await fileToDataUrl(file).catch(() => '');
        latestTrip = localPreviewUrl && result.media?.id
          ? { ...result.trip, media: (result.trip.media || []).map((media) => media.id === result.media.id ? { ...media, preview_url: localPreviewUrl } : media) }
          : result.trip;
        uploadedCount += 1;
      }
      setSavedTrips((current) => {
        const nextTrips = current.map((item) => item.id === trip.id ? latestTrip : item);
        window.localStorage.setItem(savedTripsKey(authUser?.id), JSON.stringify(nextTrips));
        return nextTrips;
      });
      setMessage(`${uploadedCount} ${uploadedCount === 1 ? (replacementMediaId ? 'memory replaced' : 'memory added') : 'memories added'} to your trip.`);
    } catch (error) {
      if (uploadedCount > 0) {
        setSavedTrips((current) => {
          const nextTrips = current.map((item) => item.id === trip.id ? latestTrip : item);
          window.localStorage.setItem(savedTripsKey(authUser?.id), JSON.stringify(nextTrips));
          return nextTrips;
        });
        setMessage(`${uploadedCount} ${uploadedCount === 1 ? 'memory was' : 'memories were'} added. ${error.message}`);
        return;
      }
      const previewMedia = await Promise.all(selectedFiles.map(async (file, index) => ({ id: replacementMediaId || `local-media-${Date.now()}-${index}`, url: await fileToDataUrl(file), type: file.type, name: file.name, size_bytes: file.size })));
      const nextTrips = savedTrips.map((item) => {
        if (item.id !== trip.id) return item;
        const media = replacementMediaId
          ? (item.media || []).map((existingMedia) => String(existingMedia.id || existingMedia.url || '') === replacementMediaId ? { ...existingMedia, ...previewMedia[0], preview_url: previewMedia[0].url } : existingMedia)
          : [...(item.media || []), ...previewMedia];
        return { ...item, media };
      });
      setSavedTrips(nextTrips);
      try {
        window.localStorage.setItem(savedTripsKey(authUser?.id), JSON.stringify(nextTrips));
        setMessage(`${selectedFiles.length} ${selectedFiles.length === 1 ? (replacementMediaId ? 'memory preview was replaced' : 'memory preview was') : 'memory previews were'} saved in this browser. Start FastAPI to persist them for other devices.`);
      } catch {
        setMessage(`${selectedFiles.length} ${selectedFiles.length === 1 ? (replacementMediaId ? 'memory preview was replaced' : 'memory preview was') : 'memory previews were'} added for this session. The browser storage limit was reached, so keep this tab open or start FastAPI.`);
      }
    }
  }

  async function toggleTripVisibility(trip) {
    const isPublic = !trip.is_public;
    try {
      const response = await apiFetch(`${PLANNER_API_URL}/trips/saved/${encodeURIComponent(trip.id)}/visibility`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ is_public: isPublic }) });
      if (!response.ok) throw new Error(`Visibility returned ${response.status}`);
      const result = await response.json();
      setSavedTrips((current) => {
        const nextTrips = current.map((item) => item.id === trip.id ? result.trip : item);
        window.localStorage.setItem(savedTripsKey(authUser?.id), JSON.stringify(nextTrips));
        return nextTrips;
      });
    } catch {
      const updatedTrip = { ...trip, is_public: isPublic };
      const nextTrips = savedTrips.map((item) => item.id === trip.id ? updatedTrip : item);
      setSavedTrips(nextTrips);
      window.localStorage.setItem(savedTripsKey(authUser?.id), JSON.stringify(nextTrips));
    }
    setMessage(isPublic ? 'Trip published to Explore.' : 'Trip is private again.');
  }

  async function publishTrip(trip, payload) {
    const updatedMedia = (trip.media || []).map((media, index) => {
      const mediaId = String(media.id || index);
      return Object.prototype.hasOwnProperty.call(payload.media_captions || {}, mediaId)
        ? { ...media, caption: payload.media_captions[mediaId] }
        : media;
    });
    try {
      const response = await apiFetch(`${PLANNER_API_URL}/trips/saved/${encodeURIComponent(trip.id)}/publish`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (!response.ok) throw new Error(`Publish returned ${response.status}`);
      const result = await response.json();
      setSavedTrips((current) => {
        const nextTrips = current.map((item) => item.id === trip.id ? result.trip : item);
        window.localStorage.setItem(savedTripsKey(authUser?.id), JSON.stringify(nextTrips));
        return nextTrips;
      });
      setExploreTrips((current) => current.map((item) => item.id === trip.id ? result.trip : item));
    } catch {
      const updatedTrip = { ...trip, ...payload, media: updatedMedia, is_public: true, updated_at: new Date().toISOString() };
      const nextTrips = savedTrips.map((item) => item.id === trip.id ? updatedTrip : item);
      setSavedTrips(nextTrips);
      setExploreTrips((current) => current.some((item) => item.id === trip.id) ? current.map((item) => item.id === trip.id ? updatedTrip : item) : [updatedTrip, ...current]);
      window.localStorage.setItem(savedTripsKey(authUser?.id), JSON.stringify(nextTrips));
    }
    setMessage('Trip published to Explore.');
  }

  function openSavedTrip(trip, options = {}) {
    const shouldRegenerate = options.regenerate === true;
    const shouldClone = options.clone === true;
    activeTripIdRef.current = shouldRegenerate || shouldClone ? null : trip.id;
    hasAutoGeneratedRef.current = true;
    const candidates = trip.candidate_places?.length ? trip.candidate_places : initialCandidates;
    const currentDate = getLocalTodayISO();
    const currentTime = getLocalTimeISO();
    const nextStartDate = shouldRegenerate ? currentDate : trip.start_date || startDate;
    const nextEndDate = shouldRegenerate ? currentDate : trip.end_date || estimateTripEndDate(nextStartDate, trip.route, trip.itinerary || []);
    const nextStartTime = shouldRegenerate ? currentTime : trip.start_time || startTime;
    const nextEndTime = trip.end_time || endTime;
    const nextTravellers = Number(trip.travellers ?? 4);
    const nextBudgetPerPerson = Number(trip.budget_per_person ?? 400);
    const nextAdventureLevel = Number(trip.adventure_level ?? 70);
    const nextRouteMode = trip.route_mode || 'balanced';
    const nextPreferences = (trip.preferences || []).filter((preference) => preference !== 'student-budget');
    setFrom(trip.start);
    setTo(trip.destination);
    setFromLocation(null);
    setToLocation(null);
    setRouteMode(nextRouteMode);
    setAdventureLevel(nextAdventureLevel);
    setBudgetPerPerson(nextBudgetPerPerson);
    setTravellers(nextTravellers);
    setStartDate(nextStartDate);
    setEndDate(nextEndDate);
    setStartTime(nextStartTime);
    setEndTime(nextEndTime);
    setPreferences(nextPreferences);
    setCandidatePlaces(shouldRegenerate ? initialCandidates : candidates);
    setSelectedPlaceId(shouldRegenerate ? null : candidates[0]?.id || null);
    setRoute(shouldRegenerate ? {} : trip.route || {});
    setStops(itineraryToStops(trip.itinerary || [], candidates, trip.destination));
    setRouteStats(shouldRegenerate ? { driveMinutes: 0, distanceKm: 0, confidence: 94 } : { driveMinutes: trip.route?.drive_minutes || 229, distanceKm: trip.route?.distance_km || 348, confidence: 94 });
    setCostBreakdown(trip.cost_breakdown || defaultCostBreakdown);
    setRecommendationSource(trip.recommendation_source || 'deterministic');
    setContextSummary(null);
    setEditingStopIndex(null);
    setFocusedStopIndex(null);
    setIsManagingStops(false);
    setPlaceQuery('');
    setPlaceSearchResults([]);
    setHasSearchedPlaces(false);
    setSimulationResult(null);
    setIsGenerated(!shouldRegenerate);
    navigateTo('Plan a trip');
    if (shouldRegenerate) {
      void recordAgentEvent('explore_route_used', { source_trip_id: trip.id, route: `${trip.start} → ${trip.destination}` }, null);
      void generateTrip({
        from: trip.start,
        to: trip.destination,
        startDate: nextStartDate,
        startTime: nextStartTime,
        endTime: nextEndTime,
        travellers: nextTravellers,
        budgetPerPerson: nextBudgetPerPerson,
        preferences: nextPreferences,
        adventureLevel: nextAdventureLevel,
        routeMode: nextRouteMode,
      });
      return;
    }
    if (shouldClone) {
      void recordAgentEvent('explore_route_used', { source_trip_id: trip.id, route: `${trip.start} → ${trip.destination}`, reused_checkpoints: true }, null);
      setMessage(`Loaded ${trip.title} with its saved checkpoints. This is now your editable route draft.`);
      return;
    }
    setMessage(`Opened ${trip.title}. Its saved checkpoints and route are ready to edit.`);
  }

  function goToPlanner() {
    syncTripPreferencesFromProfile({ preferences: profilePreferences, adventureLevel: profileAdventureLevel });
    setStartDate(getLocalTodayISO());
    setEndDate(getLocalTodayISO());
    setStartTime(getLocalTimeISO());
    navigateTo('Plan a trip');
  }

  function updateUserProfile(field, value) {
    setUserProfile((current) => {
      const nextProfile = { ...current, [field]: value };
      window.localStorage.setItem('vibetrip.userProfile', JSON.stringify(nextProfile));
      return nextProfile;
    });
  }

  async function saveUserProfile() {
    window.localStorage.setItem(profileDefaultsKey(authUser?.id), JSON.stringify({ preferences: profilePreferences, adventure_level: profileAdventureLevel }));
    if (!authUser || authUser.id === 'demo-user') {
      setMessage('Travel profile saved for this workspace.');
      return;
    }
    try {
      const response = await apiFetch(`${PLANNER_API_URL}/auth/me`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name: userProfile.name, home_base: userProfile.home }),
      });
      if (!response.ok) throw new Error('Profile update failed');
      const result = await response.json();
      setAuthUser(result.user);
      setUserProfile({ name: result.user.display_name, home: result.user.home_base });
      setMessage('Profile saved.');
    } catch {
      setMessage('Profile saved locally. Start FastAPI to sync account details.');
    }
  }

  function handleAuthenticated(user) {
    establishAuthenticatedSession(user);
    setMessage('Signed in. Your trips and OKF profile are now private to this account.');
  }

  async function enterDemoMode() {
    const demoUser = { id: 'demo-user', email: 'demo@vibetrip.local', display_name: 'Ernest Tan', home_base: 'Singapore' };
    try {
      const response = await apiFetch(`${PLANNER_API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: demoUser.email, password: 'vibetrip-demo', display_name: demoUser.display_name, home_base: demoUser.home_base }),
      });
      if (!response.ok) throw new Error(`Demo login returned ${response.status}`);
      const result = await response.json();
      establishAuthenticatedSession(result.user);
      setMessage('Demo workspace ready. Your saved trips and agent context are persisted locally by the API.');
    } catch {
      establishAuthenticatedSession(demoUser);
      setMessage('Demo workspace ready locally. Start FastAPI to persist trips and agent context.');
    }
  }

  function completeOnboarding() {
    if (authUser) window.localStorage.setItem(onboardingKey(authUser.id), 'true');
    syncTripPreferencesFromProfile({ preferences: profilePreferences, adventureLevel: profileAdventureLevel });
    setIsOnboarding(false);
    navigateTo('Plan a trip', { replace: true });
  }

  async function signOut() {
    try {
      await apiFetch(`${PLANNER_API_URL}/auth/logout`, { method: 'POST' });
    } catch {
      // Local demo mode and API-offline mode can still sign out in the UI.
    }
    setAuthUser(null);
    setSavedTrips([]);
    setIsOnboarding(false);
    navigateTo('Plan a trip', { replace: true });
    window.history.replaceState({}, '', '/login');
  }

  async function deleteTrip(trip) {
    try {
      const response = await apiFetch(`${PLANNER_API_URL}/trips/saved/${encodeURIComponent(trip.id)}`, { method: 'DELETE' });
      if (!response.ok) throw new Error(`Delete returned ${response.status}`);
    } catch {
      // The local copy is still removed when the API is offline.
    }
    const nextTrips = savedTrips.filter((item) => item.id !== trip.id);
    setSavedTrips(nextTrips);
    window.localStorage.setItem(savedTripsKey(authUser?.id), JSON.stringify(nextTrips));
    setMessage('Saved trip deleted.');
  }

  const [exploreTrips, setExploreTrips] = useState(exploreFallbackTrips);

  useEffect(() => {
    if (activeNav === 'Saved trips') loadSavedTrips();
    if (activeNav === 'Explore') loadExploreTrips();
  }, [activeNav]);

  const plannerPageProps = {
      profile: {
      profileSummary: tripProfileSummary, profileBalance: tripProfileBalance, profileOptions: tripProfileOptions, preferences, adventureLevel,
      onTogglePreference: toggleTripPreference, onAdventureInput: updateAdventureLevel, onAdventureCommit: commitAdventureLevel,
    },
    form: {
      from, to, routeTitle, routeModeOptions, isGenerating, plannerSource, routeStats, startDate, startTime, endTime,
      travellers, budgetPerPerson, isGenerated, message, fromLocation, toLocation, onFrom: updateFrom, onTo: updateTo, onSwap: swapLocations,
      onStartDate: (value) => { setStartDate(value); setEndDate(value); }, onStartTime: setStartTime, onEndTime: setEndTime,
      onTravellers: setTravellers, onBudget: setBudgetPerPerson, onGenerate: generateTrip,
    },
      route: {
      from, to, routeTitle, routeModeOptions, routeMode, isGenerating, plannerSource, recommendationSource, routeStats, currentRoute: route,
      googleMapsUrl, isRerouting, mapControllerRef, mapCandidates, onSelectCandidate: selectCandidate, onFocusCandidate: focusCandidate,
      destinationCandidates, onAddDestinationCandidate: addDestinationCandidate, onSaveTrip: saveCurrentTrip, isSavingTrip,
      onRouteMode: (nextMode) => { setRouteMode(nextMode); setMessage(`${routeModeOptions.find((option) => option.id === nextMode)?.label} route selected. Generate the route to update recommendations.`); },
    },
    itinerary: { stops, focusedStopIndex, editingStopIndex, isManagingStops, onToggleManager: toggleStopManager, onFocusStop: focusTimelineStop, onBeginChange: beginStopChange, onRemove: removeStop, onAddStop: addStop },
    assistant: { replacementStopIndex, onChooseReplacement: chooseReplacementStop, placeQuery, onPlaceQuery: setPlaceQuery, onSearch: searchRoutePlaces, isSearching: isSearchingPlaces, placeSearchResults, placeSearchHint, hasSearched: hasSearchedPlaces },
    budget: { costBreakdown, travellers },
    agentContextSummary: contextSummary,
  };

  const profilePageProps = {
    profileSummary, profileBalance, profileOptions: tripProfileOptions, preferences: profilePreferences, adventureLevel: profileAdventureLevel,
    onTogglePreference: toggleProfilePreference, onAdventureInput: updateProfileAdventureLevel,
  };

  if (isAuthLoading) return <main className="auth-page"><p className="auth-loading">Loading your private workspace…</p></main>;
  if (!authUser) return <AuthView onAuthenticated={handleAuthenticated} onDemoMode={enterDemoMode} />;
  if (isOnboarding) return <ProfileOnboarding profile={profilePageProps} userProfile={userProfile} onComplete={completeOnboarding} />;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark"><span /></span><span>vibetrip</span></div>
        <div className="sidebar-section-label">Workspace</div>
        <nav className="main-nav" aria-label="Main navigation">
          {navItems.map((item) => (
            <button key={item.label} className={`nav-item ${activeNav === item.label ? 'active' : ''}`} onClick={() => item.label === 'Plan a trip' && activeNav === 'Travel profile' ? goToPlanner() : navigateTo(item.label)}>
              <Icon name={item.icon} size={17} /><span>{item.label}</span>{item.label === 'Saved trips' && savedTrips.length > 0 && <span className="nav-count">{savedTrips.length}</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="tip-card"><div className="tip-icon"><Icon name="sparkles" size={15} /></div><p><strong>Trip tip</strong><br />Leave 20% of the day unplanned. That’s where the good stuff happens.</p></div>
          <div className="account-menu-wrap">
            <button className="profile-button" type="button" aria-haspopup="menu" aria-expanded={isAccountMenuOpen} onClick={() => setIsAccountMenuOpen((current) => !current)}><span className="avatar">{getInitials(userProfile.name)}</span><span className="profile-copy"><strong>{userProfile.name || 'VibeTrip traveller'}</strong></span><Icon name="chevron" size={15} /></button>
            {isAccountMenuOpen && <div className="account-menu" role="menu">
              <button type="button" role="menuitem" onClick={() => navigateTo('Travel profile')}><Icon name="users" size={15} />Travel profile</button>
              <button type="button" role="menuitem" onClick={() => { setIsAccountMenuOpen(false); signOut(); }}><Icon name="logout" size={15} />Sign out</button>
            </div>}
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <button className="mobile-menu" aria-label="Open navigation"><Icon name="menu" size={20} /></button>
          <div className="breadcrumbs"><span>My trips</span><Icon name="chevron" size={13} /><strong>{activeNav}</strong></div>
          <div className="topbar-actions"><span className="save-status"><span className="status-dot" />All changes saved</span></div>
        </header>

        <div className="content-wrap">
          {activeNav === 'Plan a trip' ? <PlannerPage {...plannerPageProps} /> : activeNav === 'Saved trips' ? <SavedTripsView trips={savedTrips} isLoading={isLoadingCollection} onOpen={openSavedTrip} onDelete={deleteTrip} onComplete={completeTrip} onUploadMedia={uploadTripMedia} onPublish={publishTrip} onToggleVisibility={toggleTripVisibility} onRefresh={loadSavedTrips} /> : activeNav === 'Travel profile' ? <ProfileView profile={profilePageProps} userProfile={userProfile} onUpdateProfile={updateUserProfile} onSaveProfile={saveUserProfile} onGoPlan={goToPlanner} /> : <ExploreView trips={exploreTrips} isLoading={isLoadingCollection} onUseTrip={(trip) => openSavedTrip(trip, { clone: true })} onRefresh={loadExploreTrips} />}
        </div>
      </main>
    </div>
  );
}

export default App;
