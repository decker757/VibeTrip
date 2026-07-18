import Icon from './Icon';
import { formatMoney, formatTripDistance, formatTripDriveTime } from '../app/formatters';

function TripCard({ trip, actionLabel, onAction, onDelete, showPrivacy = false }) {
  return (
    <article className="trip-card">
      <div className="trip-card-topline"><span className={`trip-mode-badge ${trip.route_mode || 'balanced'}`}>{trip.route_mode || 'balanced'} route</span>{showPrivacy && <span className="trip-privacy"><Icon name={trip.is_public ? 'grid' : 'bookmark'} size={12} />{trip.is_public ? 'Public' : 'Private'}</span>}</div>
      <h3>{trip.title}</h3>
      <p className="trip-route"><span>{trip.start}</span><Icon name="arrow" size={14} /><span>{trip.destination}</span></p>
      <div className="trip-card-stats"><span><Icon name="clock" size={13} />{formatTripDriveTime(trip.route)}</span><span><Icon name="map" size={13} />{formatTripDistance(trip.route)}</span><span><Icon name="wallet" size={13} />{formatMoney(trip.budget_per_person)} / person</span></div>
      <div className="trip-card-footer"><span className="trip-author">{trip.author_name || 'You · Singapore'} · {trip.itinerary?.length || 0} planned stops</span><div className="trip-card-actions"><button className="secondary-action" type="button" onClick={() => onAction(trip)}>{actionLabel}</button>{onDelete && <button className="text-danger" type="button" onClick={() => onDelete(trip)}>Delete</button>}</div></div>
    </article>
  );
}

export function SavedTripsView({ trips, isLoading, onOpen, onDelete, onRefresh }) {
  return <div className="collection-page"><div className="collection-heading"><div><p className="eyebrow">YOUR LIBRARY</p><h1>Saved trips</h1><p>Keep a draft for later, then reopen it when the group is ready to decide.</p></div><button className="secondary-action" type="button" onClick={onRefresh}><Icon name="arrow" size={14} />Refresh</button></div>{isLoading ? <div className="collection-loading" aria-live="polite">Loading your saved trips…</div> : trips.length === 0 ? <div className="empty-collection"><span className="empty-icon"><Icon name="bookmark" size={18} /></span><h2>Your next road trip starts here.</h2><p>Save a generated route from Plan a trip and it will appear in this library.</p><button className="primary-inline-action" type="button" onClick={onRefresh}>Refresh saved trips</button></div> : <div className="trip-card-grid">{trips.map((trip) => <TripCard key={trip.id} trip={trip} actionLabel="Open draft" onAction={onOpen} onDelete={onDelete} showPrivacy />)}</div>}</div>;
}

export function ExploreView({ trips, isLoading, onUseTrip, onRefresh }) {
  return <div className="collection-page"><div className="collection-heading"><div><p className="eyebrow">FROM THE VIBETRIP COMMUNITY</p><h1>Explore routes</h1><p>Borrow a good idea, then tune it to your own pace, budget, and travel profile.</p></div><button className="secondary-action" type="button" onClick={onRefresh}><Icon name="arrow" size={14} />Refresh feed</button></div><div className="explore-context"><Icon name="sparkles" size={15} /><span>Ranked for your current profile</span><strong>Local gems · {trips.length} public drafts</strong></div>{isLoading ? <div className="collection-loading" aria-live="polite">Finding trips that fit your profile…</div> : <div className="trip-card-grid">{trips.map((trip) => <TripCard key={trip.id} trip={trip} actionLabel="Use this route" onAction={onUseTrip} />)}</div>}</div>;
}
