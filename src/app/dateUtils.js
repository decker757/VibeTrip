export function getLocalTodayISO(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function getLocalTimeISO(date = new Date()) {
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${hours}:${minutes}`;
}

export function addDaysToISO(value, days) {
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + days);
  return getLocalTodayISO(date);
}

export function estimateTripEndDate(startDate, route = {}, itinerary = []) {
  const driveMinutes = Math.max(0, Number(route.drive_minutes || 0));
  const stopMinutes = itinerary.reduce((total, stop) => total + Number(stop.duration_min ?? stop.duration_minutes ?? 0), 0);
  const bufferMinutes = Math.max(20, Math.round(driveMinutes * 0.2));
  const totalMinutes = driveMinutes + stopMinutes + bufferMinutes;
  const minutesPerDrivingDay = 10 * 60;
  const dayOffset = Math.max(0, Math.ceil(totalMinutes / minutesPerDrivingDay) - 1);
  return addDaysToISO(startDate, dayOffset);
}
