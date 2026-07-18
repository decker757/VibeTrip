import { useEffect, useMemo, useState } from 'react';
import Icon from './Icon';
import { formatMoney, formatTripDistance, formatTripDriveTime } from '../app/formatters';
import { PLANNER_API_URL } from '../app/plannerData';

function mediaUrl(media) {
  if (!media?.url) return '';
  return media.url.startsWith('http') || media.url.startsWith('data:') || media.url.startsWith('blob:') ? media.url : `${PLANNER_API_URL}${media.url}`;
}

const preferenceLabels = {
  'local-gems': 'Local gems',
  'slow-mornings': 'Slow mornings',
  'student-budget': 'Student budget',
  adventurous: 'More adventure',
};

function TripMedia({ trip }) {
  const media = trip.media?.[0];
  if (!media && trip.cover_image) return <div className={`trip-card-media trip-card-media-cover ${trip.route_mode || 'balanced'}`}><img src={trip.cover_image} alt={`${trip.start} to ${trip.destination} route`} loading="lazy" onError={(event) => { event.currentTarget.style.display = 'none'; }} /><span>{trip.start} → {trip.destination}</span></div>;
  if (!media) return <div className={`trip-card-media trip-card-media-placeholder ${trip.route_mode || 'balanced'}`}><Icon name="map" size={22} /><span>{trip.start} → {trip.destination}</span></div>;
  const source = mediaUrl(media);
  return <div className="trip-card-media">{media.type?.startsWith('video/') ? <video src={source} muted playsInline preload="metadata" aria-label={`${trip.title} video memory`} /> : <img src={source} alt={`${trip.title} memory`} loading="lazy" /> }<span className="media-count"><Icon name={media.type?.startsWith('video/') ? 'play' : 'image'} size={12} />{trip.media.length} {trip.media.length === 1 ? 'memory' : 'memories'}</span></div>;
}

function TripCard({ trip, actionLabel, onAction, onDelete, onComplete, onUploadMedia, onToggleVisibility, showPrivacy = false }) {
  return (
    <article className="trip-card">
      <div className="trip-card-topline"><span className={`trip-mode-badge ${trip.route_mode || 'balanced'}`}>{trip.route_mode || 'balanced'} route</span><span className={`trip-status ${trip.is_completed ? 'completed' : ''}`}><Icon name={trip.is_completed ? 'check' : 'clock'} size={12} />{trip.is_completed ? 'Completed' : 'Draft'}</span>{showPrivacy && <span className="trip-privacy"><Icon name={trip.is_public ? 'grid' : 'bookmark'} size={12} />{trip.is_public ? 'Public' : 'Private'}</span>}</div>
      {trip.preferences?.length > 0 && <div className="trip-category-list" aria-label="Trip categories">{trip.preferences.map((preference) => preferenceLabels[preference] && <span className="trip-category" key={preference}>{preferenceLabels[preference]}</span>)}</div>}
      <TripMedia trip={trip} />
      <h3>{trip.title}</h3>
      <p className="trip-route"><span>{trip.start}</span><Icon name="arrow" size={14} /><span>{trip.destination}</span></p>
      <div className="trip-card-stats"><span><Icon name="clock" size={13} />{formatTripDriveTime(trip.route)}</span><span><Icon name="map" size={13} />{formatTripDistance(trip.route)}</span><span><Icon name="wallet" size={13} />{formatMoney(trip.budget_per_person)} / person</span></div>
      <div className="trip-card-footer"><span className="trip-author">{trip.author_name || 'You · Singapore'} · {trip.itinerary?.length || 0} planned stops</span><div className="trip-card-actions"><button className="secondary-action" type="button" onClick={() => onAction(trip)}>{actionLabel}</button>{onComplete && !trip.is_completed && <button className="text-action" type="button" onClick={() => onComplete(trip)}>Mark completed</button>}{onUploadMedia && trip.is_completed && <label className="text-action upload-action">Add memory<input className="media-upload-input" type="file" accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/webm,video/quicktime" onChange={(event) => { const [file] = event.target.files || []; if (file) onUploadMedia(trip, file); event.target.value = ''; }} /></label>}{onToggleVisibility && trip.is_completed && <button className="text-action" type="button" onClick={() => onToggleVisibility(trip)}>{trip.is_public ? 'Keep private' : 'Publish'}</button>}{onDelete && <button className="text-danger" type="button" onClick={() => onDelete(trip)}>Delete</button>}</div></div>
    </article>
  );
}

export function SavedTripsView({ trips, isLoading, onOpen, onDelete, onComplete, onUploadMedia, onToggleVisibility, onRefresh }) {
  return <div className="collection-page"><div className="collection-heading"><div><p className="eyebrow">YOUR LIBRARY</p><h1>Saved trips</h1><p>Keep a draft for later, then mark it completed after the road trip when you are ready to share it.</p></div><button className="secondary-action" type="button" onClick={onRefresh}><Icon name="arrow" size={14} />Refresh</button></div>{isLoading ? <div className="collection-loading" aria-live="polite">Loading your saved trips…</div> : trips.length === 0 ? <div className="empty-collection"><span className="empty-icon"><Icon name="bookmark" size={18} /></span><h2>Your next road trip starts here.</h2><p>Save a generated route from Plan a trip and it will appear in this library.</p><button className="primary-inline-action" type="button" onClick={onRefresh}>Refresh saved trips</button></div> : <div className="trip-card-grid">{trips.map((trip) => <TripCard key={trip.id} trip={trip} actionLabel="Open draft" onAction={onOpen} onComplete={onComplete} onUploadMedia={onUploadMedia} onToggleVisibility={onToggleVisibility} onDelete={onDelete} showPrivacy />)}</div>}</div>;
}

export function ExploreView({ trips, isLoading, onUseTrip, onRefresh }) {
  const [query, setQuery] = useState('');
  const [routeFilter, setRouteFilter] = useState('all');
  const [page, setPage] = useState(1);
  const pageSize = 6;
  const filteredTrips = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return trips.filter((trip) => {
      const matchesRoute = routeFilter === 'all' || trip.route_mode === routeFilter;
      if (!matchesRoute) return false;
      if (!normalizedQuery) return true;
      const itineraryText = (trip.itinerary || []).map((stop) => `${stop.title || ''} ${stop.place || ''} ${stop.detail || ''}`).join(' ');
      const searchableText = [trip.title, trip.start, trip.destination, trip.author_name, trip.route_mode, ...(trip.preferences || []), itineraryText].join(' ').toLowerCase();
      return searchableText.includes(normalizedQuery);
    });
  }, [query, routeFilter, trips]);
  const totalPages = Math.max(1, Math.ceil(filteredTrips.length / pageSize));
  const visibleTrips = filteredTrips.slice((page - 1) * pageSize, page * pageSize);

  useEffect(() => {
    setPage((current) => Math.min(current, totalPages));
  }, [totalPages]);

  return <div className="collection-page">
    <div className="collection-heading"><div><p className="eyebrow">FROM THE VIBETRIP COMMUNITY</p><h1>Explore</h1><p>See how other exchange students travelled, then remix a route to your own pace, budget, and travel profile.</p></div><button className="secondary-action" type="button" onClick={onRefresh}><Icon name="refresh" size={14} />Refresh feed</button></div>
    <section className="explore-search" aria-label="Search the VibeTrip community">
      <label htmlFor="explore-search-input">Find a trip idea</label>
      <div className="explore-search-row"><Icon name="search" size={18} /><input id="explore-search-input" type="search" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder="Search destinations, places, or trip ideas" /><button className="explore-clear" type="button" onClick={() => { setQuery(''); setPage(1); }} disabled={!query} aria-label="Clear Explore search">Clear</button></div>
      <p>Searches the community feed. For live place recommendations, use the planner assistant.</p>
    </section>
    <div className="explore-filters" aria-label="Filter trips by route style">{[['all', 'All routes'], ['fastest', 'Fastest'], ['balanced', 'Balanced'], ['scenic', 'Scenic']].map(([value, label]) => <button type="button" key={value} className={routeFilter === value ? 'active' : ''} aria-pressed={routeFilter === value} onClick={() => { setRouteFilter(value); setPage(1); }}>{label}</button>)}</div>
    <div className="explore-context"><Icon name="sparkles" size={15} /><span>For you · ranked from your travel profile</span><strong>{filteredTrips.length} of {trips.length} public trips</strong></div>
    {isLoading ? <div className="collection-loading" aria-live="polite">Finding trips that fit your profile…</div> : filteredTrips.length === 0 ? <div className="empty-collection explore-empty"><span className="empty-icon"><Icon name="search" size={18} /></span><h2>No matching trips yet.</h2><p>Try another destination, activity, or route style. You can also use the planner assistant to search live places.</p><button className="primary-inline-action" type="button" onClick={() => { setQuery(''); setRouteFilter('all'); setPage(1); }}>Clear search</button></div> : <><div className="trip-card-grid">{visibleTrips.map((trip) => <TripCard key={trip.id} trip={trip} actionLabel="Use this route" onAction={onUseTrip} />)}</div>{totalPages > 1 && <nav className="explore-pagination" aria-label="Explore pages"><button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page === 1}>Previous</button><span aria-live="polite">Page {page} of {totalPages}</span><button type="button" onClick={() => setPage((current) => Math.min(totalPages, current + 1))} disabled={page === totalPages}>Next</button></nav>}</>}
  </div>;
}
