export function formatDuration(minutes) {
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${String(remainingMinutes).padStart(2, '0')}m`;
}

export function formatDateLabel(value) {
  if (!value) return 'Select dates';
  return new Intl.DateTimeFormat('en-SG', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(`${value}T00:00:00`));
}

function addDaysToISO(value, days) {
  if (!value) return value;
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + days);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export function formatMoney(amount) {
  return `SGD ${Number(amount || 0).toFixed(0)}`;
}

export function getInitials(name) {
  const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return 'VT';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
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
    return { time: item.time, date: item.date, day_number: item.day_number, schedule_offset_minutes: item.schedule_offset_minutes, title: item.title, place_id: item.place_id, location: associatedPlace?.location, route_progress_km: associatedPlace?.route_progress_km ?? item.route_progress_km, duration_minutes: item.duration_min || 0, duration: item.duration_min ? `${item.duration_min} min` : 'overnight', ...itemDetails };
  });
}

export function candidateToStop(candidate, time = '12:30', schedule = {}) {
  const category = candidate.category?.toLowerCase() || '';
  return {
    time, date: schedule.date, day_number: schedule.day_number, schedule_offset_minutes: schedule.schedule_offset_minutes, title: candidate.name, place: candidate.name, detail: candidate.address || 'Along the route',
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

export function addMinutesToSchedule(stop, minutes, fallbackDate) {
  const currentMinutes = timeToMinutes(stop?.time);
  if (currentMinutes == null) return { time: addMinutesToTime('', minutes), date: fallbackDate };
  const total = currentMinutes + minutes;
  const dayOffset = Math.floor(total / 1440);
  return {
    time: `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`,
    date: addDaysToISO(stop?.date || fallbackDate, dayOffset),
    day_number: Number.isFinite(stop?.day_number) ? stop.day_number + dayOffset : undefined,
    schedule_offset_minutes: Number.isFinite(stop?.schedule_offset_minutes) ? stop.schedule_offset_minutes + minutes : undefined,
  };
}

export function groupStopsByDay(stops, startDate) {
  const groups = new Map();
  stops.forEach((stop, index) => {
    const dayNumber = Number.isFinite(stop.day_number)
      ? stop.day_number
      : stop.date && startDate
        ? Math.round((Date.parse(`${stop.date}T00:00:00`) - Date.parse(`${startDate}T00:00:00`)) / 86400000) + 1
        : 1;
    const key = `${dayNumber}:${stop.date || addDaysToISO(startDate, dayNumber - 1) || ''}`;
    if (!groups.has(key)) groups.set(key, { dayNumber, date: stop.date || addDaysToISO(startDate, dayNumber - 1), stops: [] });
    groups.get(key).stops.push({ stop, index });
  });
  return [...groups.values()].sort((left, right) => left.dayNumber - right.dayNumber);
}

export function formatTravelGap(currentStop, nextStop) {
  const current = Number.isFinite(currentStop.schedule_offset_minutes) ? currentStop.schedule_offset_minutes : timeToMinutes(currentStop.time);
  const next = Number.isFinite(nextStop.schedule_offset_minutes) ? nextStop.schedule_offset_minutes : timeToMinutes(nextStop.time);
  if (current == null || next == null) return 'Flexible drive';
  const drivingMinutes = Math.max(0, next - current - (currentStop.duration_minutes || 0));
  if (drivingMinutes < 1) return 'Continue to next stop';
  const hours = Math.floor(drivingMinutes / 60);
  const minutes = drivingMinutes % 60;
  return `${hours ? `${hours}h ` : ''}${minutes ? `${minutes}m` : ''} drive`.trim();
}
