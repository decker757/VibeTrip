import { useState } from 'react';
import Icon from './Icon';
import { formatMoney, formatTripDistance, formatTripDriveTime } from '../app/formatters';
import { isVideoMedia, resolveMediaUrl } from '../app/media';

const preferenceLabels = {
  'local-gems': 'Local gems',
  'slow-mornings': 'Slow mornings',
  'student-budget': 'Student budget',
  adventurous: 'More adventure',
};

const stopTypeLabels = {
  coffee: 'Coffee',
  fuel: 'Fuel + supplies',
  meal: 'Food stop',
  lunch: 'Food stop',
  attraction: 'Place to explore',
  scenic: 'Scenic stop',
  stay: 'Arrival',
};

function TripMemory({ media, title, index, fallbackUrl }) {
  const source = resolveMediaUrl(media);
  const handleMediaError = (event) => {
    if (fallbackUrl && !event.currentTarget.dataset.fallbackAttempted) {
      event.currentTarget.dataset.fallbackAttempted = 'true';
      event.currentTarget.src = fallbackUrl;
      return;
    }
    event.currentTarget.closest('figure')?.remove();
  };
  if (isVideoMedia(media)) {
    return <figure className={`trip-post-memory trip-post-memory-${index + 1}`}><video src={source} controls playsInline preload="metadata" aria-label={`${title} memory ${index + 1}`} onError={handleMediaError} /><figcaption>{media.caption || media.name || `Memory ${index + 1}`}</figcaption></figure>;
  }
  return <figure className={`trip-post-memory trip-post-memory-${index + 1}`}><img src={source} alt={media.caption || `${title} memory ${index + 1}`} loading="lazy" onError={handleMediaError} /><figcaption>{media.caption || media.name || `Memory ${index + 1}`}</figcaption></figure>;
}

function TripMemoryCarousel({ memories, title, fallbackUrl }) {
  const [activeIndex, setActiveIndex] = useState(0);
  const hasMultipleMemories = memories.length > 1;

  const move = (offset) => {
    setActiveIndex((currentIndex) => (currentIndex + offset + memories.length) % memories.length);
  };

  const handleKeyDown = (event) => {
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      move(-1);
    }
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      move(1);
    }
  };

  return <div className="trip-post-carousel-shell">
    <div className="trip-post-carousel" role="region" aria-roledescription="carousel" aria-label={`${title} memories`} tabIndex={0} onKeyDown={handleKeyDown}>
      {hasMultipleMemories && <>
        <button className="trip-post-carousel-control previous" type="button" aria-label="Show previous memory" onClick={() => move(-1)}><Icon name="chevron" size={19} /></button>
        <button className="trip-post-carousel-control next" type="button" aria-label="Show next memory" onClick={() => move(1)}><Icon name="chevron" size={19} /></button>
      </>}
      <TripMemory media={memories[activeIndex]} title={title} index={activeIndex} fallbackUrl={fallbackUrl} />
    </div>
    {hasMultipleMemories && <div className="trip-post-carousel-footer">
      <div className="trip-post-carousel-dots" aria-label="Choose a memory">
        {memories.map((media, index) => <button key={media.id || `${media.url}-${index}`} className={`trip-post-carousel-dot${activeIndex === index ? ' active' : ''}`} type="button" aria-label={`Show memory ${index + 1}`} aria-current={activeIndex === index ? 'true' : undefined} onClick={() => setActiveIndex(index)}><span /></button>)}
      </div>
      <span>Memory {activeIndex + 1} of {memories.length}</span>
    </div>}
  </div>;
}

export default function TripPostDetail({ trip, onBack, onUseTrip }) {
  const memories = (trip.media || []).slice(0, 5);
  const itinerary = trip.itinerary || [];
  const preferences = (trip.preferences || []).map((preference) => preferenceLabels[preference]).filter(Boolean);

  return <div className="trip-post-detail">
    <button className="trip-post-back" type="button" onClick={onBack}><Icon name="chevron" size={15} />Back to Explore</button>
    <header className="trip-post-heading">
      <div>
        <p className="eyebrow">COMMUNITY TRIP</p>
        <h1>{trip.title}</h1>
        <p className="trip-post-author">{trip.author_name || 'VibeTrip traveller'} · shared a completed route</p>
      </div>
      <button className="primary-inline-action trip-post-use" type="button" onClick={() => onUseTrip(trip)}><Icon name="compass" size={15} />Use this route</button>
    </header>

    <section className="trip-post-route" aria-label="Trip route">
      <span>{trip.start}</span><Icon name="arrow" size={16} /><strong>{trip.destination}</strong>
    </section>

    {memories.length > 0 ? <section className="trip-post-gallery" aria-label={`Trip memories, ${memories.length} uploaded`}><div className="trip-post-gallery-heading"><div><p className="eyebrow">TRIP MEMORIES</p><h2>What {trip.author_name?.split(' · ')[0] || 'they'} saw along the way</h2></div><span>{memories.length} {memories.length === 1 ? 'memory' : 'memories'}</span></div><TripMemoryCarousel memories={memories} title={trip.title} fallbackUrl={trip.cover_image_fallback} /></section> : trip.cover_image ? <section className="trip-post-gallery"><div className="trip-post-gallery-heading"><div><p className="eyebrow">TRIP COVER</p><h2>The route at a glance</h2></div></div><div className="trip-post-cover"><img src={trip.cover_image} alt={`${trip.start} to ${trip.destination} route cover`} /><span>Route cover · no memories uploaded yet</span></div></section> : null}

    <div className="trip-post-content-grid">
      <section className="trip-post-stops" aria-labelledby="trip-post-stops-heading"><p className="eyebrow">THE JOURNEY</p><h2 id="trip-post-stops-heading">Travelled through</h2><p className="trip-post-section-copy">The stops this traveller chose between {trip.start} and {trip.destination}.</p>{itinerary.length > 0 ? <ol>{itinerary.map((stop, index) => <li key={`${stop.title || 'stop'}-${index}`}><span className="trip-post-stop-number">{String(index + 1).padStart(2, '0')}</span><div><strong>{stop.title || stop.name || 'Planned stop'}</strong><span>{stopTypeLabels[stop.kind] || stop.category || 'Planned stop'}{stop.place || stop.detail ? ` · ${stop.place || stop.detail}` : ''}</span></div></li>)}</ol> : <p className="trip-post-empty">This post has no saved stop list yet.</p>}</section>
      <aside className="trip-post-summary" aria-label="Route snapshot"><p className="eyebrow">ROUTE SNAPSHOT</p><h2>{trip.route_mode || 'balanced'} route</h2><div className="trip-post-stats"><span><Icon name="clock" size={16} />{formatTripDriveTime(trip.route)}</span><span><Icon name="map" size={16} />{formatTripDistance(trip.route)}</span><span><Icon name="wallet" size={16} />{formatMoney(trip.budget_per_person)} / person</span></div>{preferences.length > 0 && <div className="trip-post-preferences">{preferences.map((preference) => <span key={preference}>{preference}</span>)}</div>}<button className="primary-inline-action trip-post-use-bottom" type="button" onClick={() => onUseTrip(trip)}>Use this route</button></aside>
    </div>
  </div>;
}
