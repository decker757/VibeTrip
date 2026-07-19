import { useEffect, useMemo, useRef, useState } from 'react';
import Icon from './Icon';
import { formatMoney, formatTripDistance, formatTripDriveTime } from '../app/formatters';
import { MEDIA_ACCEPT, MAX_TRIP_MEDIA, isVideoMedia, resolveMediaUrl } from '../app/media';
import { decodePolyline } from '../app/mapGeometry';
import TripPostDetail from './TripPostDetail';

const preferenceLabels = {
  'local-gems': 'Local gems',
  'slow-mornings': 'Slow mornings',
  adventurous: 'More adventure',
};

function routePreviewPath(points) {
  if (points.length < 2) return '';
  const lngs = points.map((point) => point.lng);
  const lats = points.map((point) => point.lat);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const lngSpan = Math.max(maxLng - minLng, 0.0001);
  const latSpan = Math.max(maxLat - minLat, 0.0001);
  const width = 800;
  const height = 260;
  const pad = 34;
  return points.map((point) => {
    const x = pad + ((point.lng - minLng) / lngSpan) * (width - pad * 2);
    const y = height - pad - ((point.lat - minLat) / latSpan) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
}

function mediaReplaceProps(onReplaceMedia, targetMedia = null) {
  if (!onReplaceMedia) return {};
  const activate = (event) => {
    if (event.target.closest('button, video')) return;
    onReplaceMedia(targetMedia);
  };
  return {
    role: 'button',
    tabIndex: 0,
    'aria-label': targetMedia ? 'Replace this memory' : 'Add trip memories',
    onClick: activate,
    onKeyDown: (event) => {
      if ((event.key === 'Enter' || event.key === ' ') && !event.target.closest('button, video')) {
        event.preventDefault();
        onReplaceMedia(targetMedia);
      }
    },
  };
}

function RoutePreviewMedia({ trip, onReplaceMedia }) {
  const replaceProps = mediaReplaceProps(onReplaceMedia);
  const points = decodePolyline(trip.route?.polyline || '');
  const path = routePreviewPath(points);
  if (!path) return <div {...replaceProps} className={`trip-card-media trip-card-media-placeholder ${trip.route_mode || 'balanced'}${onReplaceMedia ? ' is-replaceable' : ''}`}><Icon name="map" size={22} /><span>{trip.start} → {trip.destination}</span></div>;
  const startPoint = path.split(' ')[0].split(',');
  const endPoint = path.split(' ').slice(-1)[0].split(',');
  return <div {...replaceProps} className={`trip-card-media trip-card-route-preview ${trip.route_mode || 'balanced'}${onReplaceMedia ? ' is-replaceable' : ''}`}>
    <svg viewBox="0 0 800 260" role="img" aria-label={`Route preview from ${trip.start} to ${trip.destination}`}>
      <defs><linearGradient id={`route-preview-${trip.id}`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#d9e8d5" /><stop offset="0.52" stopColor="#d6e4e6" /><stop offset="1" stopColor="#f0dfb8" /></linearGradient></defs>
      <rect width="800" height="260" fill={`url(#route-preview-${trip.id})`} />
      <path className="route-preview-grid" d="M0 58H800 M0 130H800 M0 202H800 M160 0V260 M320 0V260 M480 0V260 M640 0V260" />
      <polyline className="route-preview-road" points={path} />
      <polyline className="route-preview-line" points={path} />
      <circle className="route-preview-start" cx={startPoint[0]} cy={startPoint[1]} r="8" />
      <circle className="route-preview-end" cx={endPoint[0]} cy={endPoint[1]} r="8" />
    </svg>
    <span>{trip.start} → {trip.destination}</span>
  </div>;
}

function TripMedia({ trip, preferRoutePreview = false, onReplaceMedia }) {
  const memories = Array.isArray(trip.media) ? trip.media.slice(0, MAX_TRIP_MEDIA) : [];
  const media = memories[0];
  const memoryCount = memories.length;
  const memorySignature = memories.map((memory) => `${memory.id || ''}:${memory.url || ''}:${memory.preview_url ? memory.preview_url.slice(0, 64) : ''}`).join('|');
  const [activeMemoryIndex, setActiveMemoryIndex] = useState(0);
  const [unavailableMemoryKeys, setUnavailableMemoryKeys] = useState(() => new Set());
  const handleImageError = (event) => {
    if (trip.cover_image_fallback && !event.currentTarget.dataset.fallbackAttempted) {
      event.currentTarget.dataset.fallbackAttempted = 'true';
      event.currentTarget.src = trip.cover_image_fallback;
      return;
    }
    event.currentTarget.style.display = 'none';
  };
  useEffect(() => {
    setActiveMemoryIndex(0);
    setUnavailableMemoryKeys(new Set());
  }, [trip.id, memoryCount, memorySignature]);

  if (preferRoutePreview && memoryCount > 0) {
    const activeMemory = memories[Math.min(activeMemoryIndex, memoryCount - 1)];
    const source = resolveMediaUrl(activeMemory);
    const activeMemoryKey = String(activeMemory.id || activeMemory.url || activeMemoryIndex);
    const markMemoryUnavailable = () => setUnavailableMemoryKeys((current) => new Set(current).add(activeMemoryKey));
    const showPrevious = () => setActiveMemoryIndex((current) => (current - 1 + memoryCount) % memoryCount);
    const showNext = () => setActiveMemoryIndex((current) => (current + 1) % memoryCount);
    return <div {...mediaReplaceProps(onReplaceMedia, activeMemory)} className={`trip-card-media trip-card-memory-carousel${onReplaceMedia ? ' is-replaceable' : ''}`} role="group" aria-roledescription="carousel" aria-label={`${trip.title} memories`}>
      {unavailableMemoryKeys.has(activeMemoryKey) ? <div className="trip-card-media-unavailable"><Icon name={isVideoMedia(activeMemory) ? 'play' : 'image'} size={22} /><span>Memory unavailable</span><small>Re-upload this item to restore its preview.</small></div> : isVideoMedia(activeMemory) ? <video src={source} muted playsInline preload="metadata" aria-label={`Video memory ${activeMemoryIndex + 1} of ${memoryCount}`} onError={markMemoryUnavailable} /> : <img src={source} alt={`${trip.title} memory ${activeMemoryIndex + 1} of ${memoryCount}`} loading="lazy" onError={markMemoryUnavailable} />}
      {memoryCount > 1 && <>
        <button className="trip-card-memory-control previous" type="button" onClick={showPrevious} aria-label="Show previous memory"><Icon name="arrow" size={15} /></button>
        <button className="trip-card-memory-control next" type="button" onClick={showNext} aria-label="Show next memory"><Icon name="arrow" size={15} /></button>
        <div className="trip-card-memory-dots" aria-label="Choose a memory">{memories.map((memory, index) => <button className={`trip-card-memory-dot${index === activeMemoryIndex ? ' active' : ''}`} type="button" key={memory.id || `${memory.url}-${index}`} onClick={() => setActiveMemoryIndex(index)} aria-label={`Show memory ${index + 1}`} aria-current={index === activeMemoryIndex ? 'true' : undefined}><span /></button>)}</div>
      </>}
      <span className="media-count" aria-live="polite"><Icon name={isVideoMedia(activeMemory) ? 'play' : 'image'} size={12} />{activeMemoryIndex + 1} / {memoryCount} {memoryCount === 1 ? 'memory' : 'memories'}</span>
    </div>;
  }
  if ((preferRoutePreview || !trip.cover_image) && memoryCount === 0 && trip.route?.polyline) return <RoutePreviewMedia trip={trip} onReplaceMedia={onReplaceMedia} />;
  if (trip.cover_image) return <div {...mediaReplaceProps(onReplaceMedia)} className={`trip-card-media trip-card-media-cover ${trip.route_mode || 'balanced'}${memoryCount > 0 ? ' has-memory-count' : ''}${onReplaceMedia ? ' is-replaceable' : ''}`}><img src={trip.cover_image} alt={`${trip.start} to ${trip.destination} route`} loading="lazy" onError={handleImageError} /><span>{trip.start} → {trip.destination}</span>{memoryCount > 0 && <span className="media-count"><Icon name="image" size={12} />{memoryCount} {memoryCount === 1 ? 'memory' : 'memories'}</span>}</div>;
  if (!media) return <div {...mediaReplaceProps(onReplaceMedia)} className={`trip-card-media trip-card-media-placeholder ${trip.route_mode || 'balanced'}${onReplaceMedia ? ' is-replaceable' : ''}`}><Icon name="map" size={22} /><span>{trip.start} → {trip.destination}</span></div>;
  const source = resolveMediaUrl(media);
  return <div {...mediaReplaceProps(onReplaceMedia)} className={`trip-card-media${onReplaceMedia ? ' is-replaceable' : ''}`}>{isVideoMedia(media) ? <video src={source} muted playsInline preload="metadata" aria-label={`${trip.title} video memory`} /> : <img src={source} alt={`${trip.title} memory`} loading="lazy" onError={handleImageError} /> }<span className="media-count"><Icon name={isVideoMedia(media) ? 'play' : 'image'} size={12} />{memoryCount} {memoryCount === 1 ? 'memory' : 'memories'}</span></div>;
}

function suggestedPostTitle(trip) {
  const destination = (trip.destination || 'your destination').split(',')[0];
  const modeTitle = { scenic: 'A scenic day of good detours', fastest: 'The essentials, without the fuss', balanced: 'A balanced day on the road' }[trip.route_mode] || 'A day worth remembering';
  return `${modeTitle} in ${destination}`;
}

function PublishTripModal({ trip, onClose, onSubmit, isSubmitting }) {
  const memories = (trip.media || []).slice(0, MAX_TRIP_MEDIA);
  const [title, setTitle] = useState(trip.title || suggestedPostTitle(trip));
  const [postCaption, setPostCaption] = useState(trip.post_caption || '');
  const [mediaCaptions, setMediaCaptions] = useState(() => Object.fromEntries(memories.map((media, index) => [String(media.id || index), media.caption || ''])));

  useEffect(() => {
    const handleKeyDown = (event) => { if (event.key === 'Escape' && !isSubmitting) onClose(); };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isSubmitting, onClose]);

  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !isSubmitting) onClose(); }}>
    <section className="publish-modal" role="dialog" aria-modal="true" aria-labelledby="publish-trip-title">
      <div className="publish-modal-heading"><div><p className="eyebrow">SHARE TO EXPLORE</p><h2 id="publish-trip-title">Tell the story of this trip.</h2><p>Give the route a title and a little context, like a Strava trip recap.</p></div><button className="modal-close" type="button" onClick={onClose} disabled={isSubmitting} aria-label="Close publish dialog">×</button></div>
      <form onSubmit={(event) => { event.preventDefault(); onSubmit({ title: title.trim(), post_caption: postCaption.trim(), media_captions: mediaCaptions }); }}>
        <label className="publish-field"><span>Post title</span><input autoFocus required maxLength={140} value={title} onChange={(event) => setTitle(event.target.value)} /><small>Suggested from your route and route style. You can change it.</small></label>
        <label className="publish-field"><span>Caption</span><textarea rows={4} maxLength={2000} value={postCaption} onChange={(event) => setPostCaption(event.target.value)} placeholder="What made this route worth sharing?" /></label>
        {memories.length > 0 && <fieldset className="publish-memory-fields"><legend>Memory captions <small>optional</small></legend>{memories.map((media, index) => { const source = resolveMediaUrl(media); const mediaKey = String(media.id || index); return <label className="publish-memory-field" key={media.id || `${media.url}-${index}`}><span className="publish-memory-label">{isVideoMedia(media) ? 'Video' : 'Photo'} {index + 1}</span><span className="publish-memory-preview">{isVideoMedia(media) ? <video src={source} muted playsInline preload="metadata" controls aria-label={`Preview video ${index + 1}`} /> : <img src={source} alt={`Preview photo ${index + 1}`} loading="lazy" />}</span><input maxLength={240} value={mediaCaptions[mediaKey] || ''} onChange={(event) => setMediaCaptions((current) => ({ ...current, [mediaKey]: event.target.value }))} placeholder="Add a short caption" /></label>; })}</fieldset>}
        <div className="publish-modal-actions"><button className="secondary-action" type="button" onClick={onClose} disabled={isSubmitting}>Cancel</button><button className="primary-inline-action" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Publishing…' : 'Publish to Explore'}</button></div>
      </form>
    </section>
  </div>;
}

function ConfirmDeleteModal({ trip, onClose, onConfirm, isDeleting }) {
  useEffect(() => {
    const handleKeyDown = (event) => { if (event.key === 'Escape' && !isDeleting) onClose(); };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isDeleting, onClose]);
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !isDeleting) onClose(); }}><section className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="delete-trip-title"><p className="eyebrow">DELETE SAVED TRIP</p><h2 id="delete-trip-title">Delete “{trip.title}”?</h2><p>This removes the saved route from your library. A published Explore post will no longer be available either.</p><div className="publish-modal-actions"><button className="secondary-action" type="button" onClick={onClose} disabled={isDeleting}>Keep trip</button><button className="danger-action" type="button" onClick={onConfirm} disabled={isDeleting}>{isDeleting ? 'Deleting…' : 'Delete trip'}</button></div></section></div>;
}

function TripCard({ trip, actionLabel, onAction, onOpenTrip, onDelete, onComplete, onUploadMedia, onPublish, onToggleVisibility, showPrivacy = false }) {
  const uploadInputRef = useRef(null);
  const replacementMediaIdRef = useRef(null);
  function openMediaPicker(media = null) {
    replacementMediaIdRef.current = media ? String(media.id || media.url || '') : null;
    uploadInputRef.current?.click();
  }
  function handleCardClick(event) {
    if (!onOpenTrip || event.target.closest('button, a, input, label')) return;
    onOpenTrip(trip);
  }

  function handleCardKeyDown(event) {
    if (!onOpenTrip || event.target.closest('button, a, input, label')) return;
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onOpenTrip(trip);
    }
  }

  return (
    <article className={`trip-card ${onOpenTrip ? 'explore-trip-card' : ''}`} onClick={handleCardClick} onKeyDown={handleCardKeyDown} tabIndex={onOpenTrip ? 0 : undefined} aria-label={onOpenTrip ? `View ${trip.title}` : undefined}>
      <div className="trip-card-topline"><span className={`trip-mode-badge ${trip.route_mode || 'balanced'}`}>{trip.route_mode || 'balanced'} route</span>{showPrivacy && <span className="trip-privacy"><Icon name={trip.is_public ? 'grid' : 'bookmark'} size={12} />{trip.is_public ? 'Public' : 'Private'}</span>}</div>
      {trip.preferences?.length > 0 && <div className="trip-category-list" aria-label="Trip categories">{trip.preferences.map((preference) => preferenceLabels[preference] && <span className="trip-category" key={preference}>{preferenceLabels[preference]}</span>)}</div>}
      <TripMedia trip={trip} preferRoutePreview={showPrivacy} onReplaceMedia={onUploadMedia ? openMediaPicker : undefined} />
      <h3>{trip.title}</h3>
      <div className="trip-card-route-row"><p className="trip-route"><span>{trip.start}</span><Icon name="arrow" size={14} /><span>{trip.destination}</span></p><div className="trip-card-stats"><span><Icon name="clock" size={13} />{formatTripDriveTime(trip.route)}</span><span><Icon name="map" size={13} />{formatTripDistance(trip.route)}</span><span><Icon name="wallet" size={13} />{formatMoney(trip.budget_per_person)} / person</span></div></div>
      <div className="trip-card-footer"><span className="trip-author">{trip.author_name || 'You · Singapore'} · {trip.itinerary?.length || 0} planned stops</span><div className="trip-card-actions">{onOpenTrip && <button className="secondary-action" type="button" onClick={() => onOpenTrip(trip)}>View trip story</button>}{onAction && <button className="secondary-action" type="button" onClick={() => onAction(trip)}>{actionLabel}</button>}{onComplete && !trip.is_completed && <button className="secondary-action" type="button" onClick={() => onComplete(trip)}>Mark trip complete</button>}{onUploadMedia && <><button className="secondary-action" type="button" title={`Add memories (${MAX_TRIP_MEDIA} maximum)`} onClick={() => openMediaPicker()}>Add memories</button><input ref={uploadInputRef} className="media-upload-input" type="file" multiple accept={MEDIA_ACCEPT} onChange={(event) => { const files = Array.from(event.target.files || []); const replacementMediaId = replacementMediaIdRef.current; if (files.length) onUploadMedia(trip, files, replacementMediaId); replacementMediaIdRef.current = null; event.target.value = ''; }} /></>}{onPublish && trip.is_completed && !trip.is_public && <button className="primary-inline-action" type="button" onClick={() => onPublish(trip)}>Publish to Explore</button>}{onToggleVisibility && trip.is_completed && trip.is_public && <button className="secondary-action" type="button" title="Remove this trip from Explore" onClick={() => onToggleVisibility(trip)}>Make private</button>}{onDelete && <button className="danger-action" type="button" onClick={() => onDelete(trip)}>Delete</button>}</div></div>
    </article>
  );
}

export function SavedTripsView({ trips, isLoading, onOpen, onDelete, onComplete, onUploadMedia, onPublish, onToggleVisibility, onRefresh }) {
  const [publishCandidate, setPublishCandidate] = useState(null);
  const [deleteCandidate, setDeleteCandidate] = useState(null);
  const [isPublishing, setIsPublishing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  async function handlePublish(payload) {
    if (!publishCandidate || !onPublish) return;
    setIsPublishing(true);
    try { await onPublish(publishCandidate, payload); setPublishCandidate(null); } finally { setIsPublishing(false); }
  }

  async function handleDelete() {
    if (!deleteCandidate || !onDelete) return;
    setIsDeleting(true);
    try { await onDelete(deleteCandidate); setDeleteCandidate(null); } finally { setIsDeleting(false); }
  }

  return <div className="collection-page"><div className="collection-heading"><div><p className="eyebrow">YOUR LIBRARY</p><h1>Saved trips</h1><p>Keep a draft for later, then mark it completed after the road trip when you are ready to share it.</p></div><button className="secondary-action" type="button" onClick={onRefresh}><Icon name="refresh" size={14} />Refresh</button></div>{isLoading ? <div className="collection-loading" aria-live="polite">Loading your saved trips…</div> : trips.length === 0 ? <div className="empty-collection"><span className="empty-icon"><Icon name="bookmark" size={18} /></span><h2>Your next road trip starts here.</h2><p>Save a generated route from Plan a trip and it will appear in this library.</p><button className="primary-inline-action" type="button" onClick={onRefresh}>Refresh saved trips</button></div> : <div className="trip-card-grid">{trips.map((trip) => <TripCard key={trip.id} trip={trip} actionLabel={trip.is_completed ? 'Open trip' : 'Open draft'} onAction={onOpen} onComplete={onComplete} onUploadMedia={onUploadMedia} onPublish={() => setPublishCandidate(trip)} onToggleVisibility={onToggleVisibility} onDelete={() => setDeleteCandidate(trip)} showPrivacy />)}</div>}{publishCandidate && <PublishTripModal trip={publishCandidate} onClose={() => setPublishCandidate(null)} onSubmit={handlePublish} isSubmitting={isPublishing} />}{deleteCandidate && <ConfirmDeleteModal trip={deleteCandidate} onClose={() => setDeleteCandidate(null)} onConfirm={handleDelete} isDeleting={isDeleting} />}</div>;
}

export function ExploreView({ trips, isLoading, onUseTrip, onRefresh }) {
  const [query, setQuery] = useState('');
  const [routeFilter, setRouteFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [selectedTrip, setSelectedTrip] = useState(null);
  const pageSize = 6;
  const previousPageRef = useRef(page);
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
  const visibleStart = filteredTrips.length === 0 ? 0 : (page - 1) * pageSize + 1;
  const visibleEnd = Math.min(page * pageSize, filteredTrips.length);

  useEffect(() => {
    setPage((current) => Math.min(current, totalPages));
  }, [totalPages]);

  useEffect(() => {
    if (previousPageRef.current === page) return;
    previousPageRef.current = page;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [page]);

  if (selectedTrip) return <TripPostDetail trip={selectedTrip} onBack={() => setSelectedTrip(null)} onUseTrip={onUseTrip} />;

  return <div className="collection-page">
    <div className="collection-heading"><div><p className="eyebrow">FROM THE VIBETRIP COMMUNITY</p><h1>Explore</h1><p>See how other exchange students travelled, then remix a route to your own pace, budget, and travel profile.</p></div><button className="secondary-action" type="button" onClick={onRefresh}><Icon name="refresh" size={14} />Refresh feed</button></div>
    <section className="explore-search" aria-label="Search the VibeTrip community">
      <label htmlFor="explore-search-input">Find a trip idea</label>
      <div className="explore-search-row"><Icon name="search" size={18} /><input id="explore-search-input" type="search" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder="Search destinations, places, or trip ideas" /><button className="explore-clear" type="button" onClick={() => { setQuery(''); setPage(1); }} disabled={!query} aria-label="Clear Explore search">Clear</button></div>
      <p>Searches the community feed. For live place recommendations, use the planner assistant.</p>
    </section>
    <div className="explore-filters" aria-label="Filter trips by route style">{[['all', 'All routes'], ['fastest', 'Fastest'], ['balanced', 'Balanced'], ['scenic', 'Scenic']].map(([value, label]) => <button type="button" key={value} className={routeFilter === value ? 'active' : ''} aria-pressed={routeFilter === value} onClick={() => { setRouteFilter(value); setPage(1); }}>{label}</button>)}</div>
    {filteredTrips.length > 0 && <div className="explore-results-meta" aria-live="polite">Showing {visibleStart}–{visibleEnd} of {filteredTrips.length} public trips</div>}
    {isLoading ? <div className="collection-loading" aria-live="polite">Finding trips that fit your profile…</div> : filteredTrips.length === 0 ? <div className="empty-collection explore-empty"><span className="empty-icon"><Icon name="search" size={18} /></span><h2>No matching trips yet.</h2><p>Try another destination, activity, or route style. You can also use the planner assistant to search live places.</p><button className="primary-inline-action" type="button" onClick={() => { setQuery(''); setRouteFilter('all'); setPage(1); }}>Clear search</button></div> : <><div className="trip-card-grid">{visibleTrips.map((trip) => <TripCard key={trip.id} trip={trip} actionLabel="Use this route" onAction={onUseTrip} onOpenTrip={setSelectedTrip} />)}</div>{totalPages > 1 && <nav className="explore-pagination" aria-label="Explore pages"><button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page === 1}>Previous</button><span aria-live="polite">Page {page} of {totalPages}</span><button type="button" onClick={() => setPage((current) => Math.min(totalPages, current + 1))} disabled={page === totalPages}>Next</button></nav>}</>}
  </div>;
}
