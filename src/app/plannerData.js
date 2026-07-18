export const PLANNER_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const navItems = [
  { label: 'Plan a trip', icon: 'compass' },
  { label: 'Explore', icon: 'sparkles' },
  { label: 'Saved trips', icon: 'bookmark', count: '3' },
];

export const initialStops = [
  { time: '08:10', title: 'Coffee stop', place: 'The Coffee Exchange', detail: 'Providence, RI', type: 'coffee', duration: '25 min' },
  { time: '11:30', title: 'Lunch with a view', place: 'The Lobster Shack', detail: 'Mystic, CT', type: 'lunch', duration: '55 min' },
  { time: '13:35', title: 'Fuel up', place: 'Shell · Exit 8', detail: 'New Haven, CT', type: 'fuel', duration: '15 min' },
  { time: '15:40', title: 'Check-in', place: 'The Hoxton, Williamsburg', detail: 'Brooklyn, NY', type: 'stay', duration: 'overnight' },
];

export const initialCandidates = [
  { id: 'demo-coffee', name: 'The Coffee Exchange', category: 'Cafe', address: 'Providence, RI', rating: 4.6, review_count: 825, price_label: '$', cost_type: 'food', estimated_cost_sgd: 12, cost_label: '~SGD 12/person', cost_note: 'Estimated from Google price level.', detour_minutes: 3, enjoyment_score: 86, crowd_risk: 'low', open_now: true, recommendation_scope: 'along_route', recommendation_kind: 'practical', reason: 'A calm reset with strong reviews and almost no route drift.' },
  { id: 'demo-lunch', name: 'The Lobster Shack', category: 'Restaurant', address: 'Mystic, CT', rating: 4.5, review_count: 1100, price_label: '$$', cost_type: 'food', estimated_cost_sgd: 22, cost_label: '~SGD 22/person', cost_note: 'Estimated from Google price level.', detour_minutes: 12, enjoyment_score: 88, crowd_risk: 'medium', open_now: true, recommendation_scope: 'along_route', recommendation_kind: 'practical', reason: 'Best balance of a memorable meal, student budget, and route fit.' },
  { id: 'demo-attraction', name: 'Mystic Seaport Museum', category: 'Tourist attraction', address: 'Mystic, CT', rating: 4.7, review_count: 3200, price_label: '$$', cost_type: 'admission', estimated_cost_sgd: null, cost_label: 'Ticket price to verify', cost_note: 'Check the official site before committing.', detour_minutes: 14, enjoyment_score: 81, crowd_risk: 'high', open_now: true, recommendation_scope: 'along_route', recommendation_kind: 'scenic', reason: 'High delight potential, but arrive before the afternoon crowd.' },
  { id: 'demo-fuel', name: 'Shell · Exit 8', category: 'Gas station', address: 'New Haven, CT', rating: 4.1, review_count: 410, price_label: '$', cost_type: 'none', estimated_cost_sgd: 0, cost_label: 'No entry cost expected', cost_note: 'Fuel is estimated separately.', detour_minutes: 2, enjoyment_score: 72, crowd_risk: 'low', open_now: true, recommendation_scope: 'along_route', recommendation_kind: 'practical', reason: 'Low-friction fuel and bathroom stop before the final leg.' },
  { id: 'demo-destination', name: 'Brooklyn Bridge Park', category: 'Tourist attraction', address: 'Brooklyn, NY', rating: 4.8, review_count: 8400, price_label: 'Free', cost_type: 'none', estimated_cost_sgd: 0, cost_label: 'Free entry', cost_note: 'Check event schedules before visiting.', detour_minutes: 6, enjoyment_score: 84, crowd_risk: 'high', open_now: true, recommendation_scope: 'destination', recommendation_kind: 'scenic', reason: 'A free destination highlight with skyline views.' },
];

export const profileOptions = [
  { id: 'local-gems', label: 'Local gems', icon: 'sparkles' },
  { id: 'slow-mornings', label: 'Slow mornings', icon: 'clock' },
  { id: 'student-budget', label: 'Student budget', icon: 'wallet' },
  { id: 'adventurous', label: 'More adventure', icon: 'compass' },
];

export const routeModeOptions = [
  { id: 'fastest', label: 'Fastest', description: 'Bare essentials', detail: 'Keeps the route tight and limits recommendations.' },
  { id: 'balanced', label: 'Balanced', description: 'Worthwhile detours', detail: 'Adds one or two stops that earn the time.' },
  { id: 'scenic', label: 'Scenic', description: 'Intermediate gems', detail: 'Lets memorable places shape the way there.' },
];

export const exploreFallbackTrips = [
  { id: 'fallback-boston-new-york', author_name: 'Maya · SMU exchange', title: 'Coastline, coffee, and a little history', start: 'Boston, MA', destination: 'New York, NY', route_mode: 'scenic', adventure_level: 78, budget_per_person: 180, travellers: 3, preferences: ['local-gems', 'adventurous'], route: { distance_km: 365, drive_minutes: 244 }, itinerary: [{ title: 'Cedar Street Café', kind: 'coffee' }, { title: 'Mystic Seaport', kind: 'attraction' }, { title: 'Dinner in Brooklyn', kind: 'meal' }], is_public: true },
  { id: 'fallback-portland-seattle', author_name: 'Daniel · NTU exchange', title: 'Rainy-day stops up the Pacific Northwest', start: 'Portland, OR', destination: 'Seattle, WA', route_mode: 'balanced', adventure_level: 56, budget_per_person: 145, travellers: 4, preferences: ['slow-mornings', 'student-budget'], route: { distance_km: 280, drive_minutes: 175 }, itinerary: [{ title: 'Farmers market coffee', kind: 'coffee' }, { title: 'Centralia lunch', kind: 'meal' }, { title: 'Fuel + convenience', kind: 'fuel' }], is_public: true },
  { id: 'fallback-munich-prague', author_name: 'Isha · SMU exchange', title: 'Munich to Prague with only the good breaks', start: 'Munich, Germany', destination: 'Prague, Czechia', route_mode: 'fastest', adventure_level: 34, budget_per_person: 120, travellers: 2, preferences: ['student-budget'], route: { distance_km: 382, drive_minutes: 260 }, itinerary: [{ title: 'Autohof fuel + snack', kind: 'fuel' }, { title: 'Quick lunch', kind: 'meal' }], is_public: true },
];

export const defaultCostBreakdown = {
  estimated_total_sgd: 0,
  estimated_per_person_sgd: 0,
  travellers: 4,
  items: [],
  unknown_admissions: [],
  assumptions: [],
};
