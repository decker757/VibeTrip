import exploreTrips from './exploreTrips.json';

export const PLANNER_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const navItems = [
  { label: 'Plan a trip', icon: 'compass' },
  { label: 'Explore', icon: 'sparkles' },
  { label: 'Saved trips', icon: 'bookmark', count: '3' },
];

export const initialStops = [
  { time: '08:10', title: 'Coffee stop', place: 'The Coffee Exchange', detail: 'Providence, RI', type: 'coffee', duration: '25 min', place_id: 'demo-coffee', route_progress_km: 65 },
  { time: '10:55', title: 'Fuel up', place: 'Shell · Exit 8', detail: 'New Haven, CT', type: 'fuel', duration: '15 min', place_id: 'demo-fuel', route_progress_km: 125 },
  { time: '12:30', title: 'Lunch with a view', place: 'The Lobster Shack', detail: 'Mystic, CT', type: 'lunch', duration: '55 min', place_id: 'demo-lunch', route_progress_km: 205 },
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
  { id: 'adventurous', label: 'More adventure', icon: 'compass' },
];

// Budget is set per trip, so it is not treated as a persistent travel-profile preference.
export const tripProfileOptions = profileOptions.filter((option) => option.id !== 'student-budget');

export const routeModeOptions = [
  { id: 'fastest', label: 'Fastest', description: 'Bare essentials + fuel', detail: 'Keeps the route tight, with a fuel stop on drives of two hours or more.' },
  { id: 'balanced', label: 'Balanced', description: 'Worthwhile detours', detail: 'Adds one or two stops that earn the time.' },
  { id: 'scenic', label: 'Scenic', description: 'Intermediate gems', detail: 'Lets memorable places shape the way there.' },
];

const exploreCoverImages = {
  'fallback-boston-new-york': 'https://images.unsplash.com/photo-1500534623283-312aade485b7?auto=format&fit=crop&w=1200&q=82',
  'fallback-portland-seattle': 'https://images.unsplash.com/photo-1448375240586-882707db888b?auto=format&fit=crop&w=1200&q=82',
  'fallback-munich-prague': 'https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=1200&q=82',
  'fallback-singapore-malacca': 'https://images.unsplash.com/photo-1525625293386-3f8f99389edd?auto=format&fit=crop&w=1200&q=82',
  'fallback-kyoto-osaka': 'https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=1200&q=82',
  'fallback-bangkok-hua-hin': 'https://images.unsplash.com/photo-1508009603885-50cf7c579365?auto=format&fit=crop&w=1200&q=82',
  'fallback-cape-town-stellenbosch': 'https://images.unsplash.com/photo-1516026672322-bc52d61a55d5?auto=format&fit=crop&w=1200&q=82',
  'fallback-nairobi-naivasha': 'https://images.unsplash.com/photo-1547471080-7cc2caa01a7e?auto=format&fit=crop&w=1200&q=82',
  'fallback-melbourne-apollo-bay': 'https://images.unsplash.com/photo-1526772662000-3f88f10405ff?auto=format&fit=crop&w=1200&q=82',
  'fallback-auckland-rotorua': 'https://images.unsplash.com/photo-1469521669194-babb45599def?auto=format&fit=crop&w=1200&q=82',
  'fallback-buenos-aires-tigre': 'https://images.unsplash.com/photo-1517457373958-b7bdd4587205?auto=format&fit=crop&w=1200&q=82',
  'fallback-santiago-valparaiso': 'https://images.unsplash.com/photo-1498307833015-e7b400441eb8?auto=format&fit=crop&w=1200&q=82',
  // This direct Unsplash image is a more reliable free source for the Marrakech seed.
  'fallback-marrakech-essaouira': 'https://images.unsplash.com/photo-1580746738099-1cb74f972feb?auto=format&fit=crop&w=1200&q=82',
};

const exploreCoverFallbacks = {
  'fallback-marrakech-essaouira': 'https://images.unsplash.com/photo-1539650116574-75c0c6d73f6e?auto=format&fit=crop&w=1200&q=82',
};

const exploreMemorySeeds = {
  'fallback-boston-new-york': [
    { url: exploreCoverImages['fallback-portland-seattle'], caption: 'A quiet forest stretch before the city.' },
    { url: exploreCoverImages['fallback-munich-prague'], caption: 'The road opens up after the morning coffee stop.' },
  ],
  'fallback-portland-seattle': [
    { url: exploreCoverImages['fallback-boston-new-york'], caption: 'Rainy roads and a warm café reset.' },
    { url: exploreCoverImages['fallback-auckland-rotorua'], caption: 'A green detour before the final leg.' },
  ],
  'fallback-munich-prague': [
    { url: exploreCoverImages['fallback-auckland-rotorua'], caption: 'A calm mountain-road pause.' },
    { url: exploreCoverImages['fallback-boston-new-york'], caption: 'The best part of the drive was between cities.' },
  ],
  'fallback-singapore-malacca': [
    { url: exploreCoverImages['fallback-bangkok-hua-hin'], caption: 'A little Southeast Asian city energy before crossing north.' },
    { url: exploreCoverImages['fallback-kyoto-osaka'], caption: 'A green pause before the food stops in Malacca.' },
  ],
  'fallback-kyoto-osaka': [
    { url: exploreCoverImages['fallback-singapore-malacca'], caption: 'An early start through the quieter streets.' },
    { url: exploreCoverImages['fallback-auckland-rotorua'], caption: 'A peaceful view between tea and street food.' },
  ],
  'fallback-bangkok-hua-hin': [
    { url: exploreCoverImages['fallback-singapore-malacca'], caption: 'The city fades as the road heads toward the coast.' },
    { url: exploreCoverImages['fallback-cape-town-stellenbosch'], caption: 'A slower stop before the beachside dinner.' },
  ],
  'fallback-cape-town-stellenbosch': [
    { url: exploreCoverImages['fallback-melbourne-apollo-bay'], caption: 'Mountain light on the way to the winelands.' },
    { url: exploreCoverImages['fallback-boston-new-york'], caption: 'A lookout worth pulling over for.' },
  ],
  'fallback-nairobi-naivasha': [
    { url: exploreCoverImages['fallback-cape-town-stellenbosch'], caption: 'Wide-open landscapes between the viewpoint stops.' },
    { url: exploreCoverImages['fallback-melbourne-apollo-bay'], caption: 'A quiet road before the lakeside lunch.' },
  ],
  'fallback-melbourne-apollo-bay': [
    { url: exploreCoverImages['fallback-nairobi-naivasha'], caption: 'Coastal light after leaving Torquay.' },
    { url: exploreCoverImages['fallback-portland-seattle'], caption: 'A forested stretch before the Twelve Apostles.' },
  ],
  'fallback-auckland-rotorua': [
    { url: exploreCoverImages['fallback-melbourne-apollo-bay'], caption: 'A long green road toward the geothermal country.' },
    { url: exploreCoverImages['fallback-cape-town-stellenbosch'], caption: 'A scenic pause before the evening soak.' },
  ],
  'fallback-buenos-aires-tigre': [
    { url: exploreCoverImages['fallback-singapore-malacca'], caption: 'A slow morning leaving the city behind.' },
    { url: exploreCoverImages['fallback-bangkok-hua-hin'], caption: 'Market colours before the riverside lunch.' },
  ],
  'fallback-santiago-valparaiso': [
    { url: exploreCoverImages['fallback-cape-town-stellenbosch'], caption: 'Mountain light on the long way to the coast.' },
    { url: exploreCoverImages['fallback-melbourne-apollo-bay'], caption: 'A roadside view before the street art walk.' },
  ],
  'fallback-marrakech-essaouira': [
    { url: 'https://images.unsplash.com/photo-1587974928442-77dc3e0dba72?auto=format&fit=crop&w=1200&q=82', caption: 'Colour and texture from the Marrakech souks.' },
    { url: 'https://images.unsplash.com/photo-1536237717235-0acadb345d8c?auto=format&fit=crop&w=1200&q=82', caption: 'A roadside pause on the way to the Atlantic.' },
  ],
};

// Real planner snapshots: regenerate with `python scripts/seed_explore_trips.py`.
export const exploreFallbackTrips = exploreTrips.map((trip) => {
  const coverImage = exploreCoverImages[trip.id];
  const seededMedia = trip.media?.length ? trip.media : (exploreMemorySeeds[trip.id] || []).map((memory, index) => ({
    ...memory,
    id: `seed-${trip.id}-memory-${index + 1}`,
    type: 'image/jpeg',
    name: `${trip.destination} memory ${index + 1}`,
  }));
  return {
    ...trip,
    cover_image: coverImage,
    cover_image_fallback: exploreCoverFallbacks[trip.id],
    media: seededMedia,
  };
});

export const defaultCostBreakdown = {
  estimated_total_sgd: 0,
  estimated_per_person_sgd: 0,
  travellers: 4,
  items: [],
  unknown_admissions: [],
  assumptions: [],
};
