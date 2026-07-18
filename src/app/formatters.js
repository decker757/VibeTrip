export function formatDuration(minutes) {
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${String(remainingMinutes).padStart(2, '0')}m`;
}

export function formatDateLabel(value) {
  if (!value) return 'Select dates';
  return new Intl.DateTimeFormat('en-SG', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(`${value}T00:00:00`));
}

export function formatMoney(amount) {
  return `SGD ${Number(amount || 0).toFixed(0)}`;
}

export function formatTripDistance(route) {
  return route?.distance_km ? `${Math.round(route.distance_km)} km` : 'Distance to calculate';
}

export function formatTripDriveTime(route) {
  return route?.drive_minutes ? formatDuration(Number(route.drive_minutes)) : 'Drive time to calculate';
}

export function buildGoogleMapsUrl(from, destination, stops) {
  const waypoints = stops
    .filter((stop) => stop.place_id && ['lunch', 'attraction'].includes(stop.type))
    .map((stop) => `${stop.place}${stop.detail && !stop.detail.includes('Along the route') ? `, ${stop.detail}` : ''}`)
    .filter((value, index, values) => values.indexOf(value) === index)
    .slice(0, 3);
  const params = new URLSearchParams({ api: '1', origin: from, destination, travelmode: 'driving' });
  if (waypoints.length > 0) params.set('waypoints', waypoints.join('|'));
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

export function buildClientCostBreakdown(route, candidate, travellers) {
  const distanceKm = Number(route?.distance_km || 0);
  const fuel = Number((distanceKm / 12 * 2.1).toFixed(2));
  const tolls = Number((distanceKm * 0.045).toFixed(2));
  const food = candidate?.cost_type === 'food' ? Number(candidate.estimated_cost_sgd || 0) * travellers : 0;
  const tickets = candidate?.cost_type === 'admission' && candidate.estimated_cost_sgd != null ? Number(candidate.estimated_cost_sgd) : 0;
  const total = Number((fuel + tolls + food + tickets).toFixed(2));
  return {
    currency: 'SGD', travellers, estimated_total_sgd: total,
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

export function itineraryToStops(itinerary, detours, destination) {
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
    return { time: item.time, title: item.title, place_id: item.place_id, location: associatedPlace?.location, route_progress_km: associatedPlace?.route_progress_km ?? item.route_progress_km, duration_minutes: item.duration_min || 0, duration: item.duration_min ? `${item.duration_min} min` : 'overnight', ...itemDetails };
  });
}

export function candidateToStop(candidate, time = '12:30') {
  const category = candidate.category?.toLowerCase() || '';
  return {
    time, title: candidate.name, place: candidate.name, detail: candidate.address || 'Along the route',
    type: category.includes('cafe') || category.includes('coffee') ? 'coffee' : category.includes('gas') || category.includes('fuel') || category.includes('convenience') || category.includes('store') ? 'fuel' : category.includes('attraction') ? 'attraction' : 'lunch',
    duration_minutes: 45, duration: '45 min', place_id: candidate.id, location: candidate.location, route_progress_km: candidate.route_progress_km,
  };
}

export function timeToMinutes(value = '') {
  const [hours, minutes] = value.split(':').map(Number);
  return Number.isFinite(hours) && Number.isFinite(minutes) ? hours * 60 + minutes : null;
}

export function addMinutesToTime(value, minutes) {
  const total = (timeToMinutes(value) ?? 0) + minutes;
  return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

export function formatTravelGap(currentStop, nextStop) {
  const current = timeToMinutes(currentStop.time);
  const next = timeToMinutes(nextStop.time);
  if (current == null || next == null) return 'Flexible drive';
  const drivingMinutes = Math.max(0, next - current - (currentStop.duration_minutes || 0));
  if (drivingMinutes < 1) return 'Continue to next stop';
  const hours = Math.floor(drivingMinutes / 60);
  const minutes = drivingMinutes % 60;
  return `${hours ? `${hours}h ` : ''}${minutes ? `${minutes}m` : ''} drive`.trim();
}
