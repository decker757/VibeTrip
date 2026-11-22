import { useState } from 'react';
import Icon from './Icon';
import LocationField from './LocationField';

const VISIT_LENGTHS = [15, 30, 45, 60, 90, 120, 150, 180, 240];

function StopIcon({ type }) {
  return <span className={`stop-icon stop-${type}`}><Icon name={type === 'fuel' ? 'fuel' : type === 'stay' ? 'suitcase' : type === 'lunch' ? 'sun' : 'compass'} size={16} /></span>;
}

// The traveller owns each stop: how long to stay, and whether a regenerate may replace it.
function StopControls({ stop, index, onChangeDuration, onToggleLock }) {
  const lengths = [...new Set([...VISIT_LENGTHS, stop.duration_minutes])].filter(Boolean).sort((a, b) => a - b);
  return (
    <div className="stop-controls" onClick={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()}>
      <label>Stay <select aria-label={`How long to stay at ${stop.title}`} value={stop.duration_minutes} onChange={(event) => onChangeDuration(index, Number(event.target.value))}>{lengths.map((minutes) => <option key={minutes} value={minutes}>{minutes} min</option>)}</select></label>
      <button type="button" className={`stop-lock ${stop.locked ? 'locked' : ''}`} aria-pressed={Boolean(stop.locked)} title={stop.locked ? 'Regenerating keeps this stop' : 'Keep this stop when regenerating'} onClick={() => onToggleLock(index)}><Icon name="lock" size={11} />{stop.locked ? 'Locked' : 'Lock'}</button>
    </div>
  );
}

export function TimelineRow({ stop, index, isLast, isFocused, isEditing, isManaging, onFocus, onChange, onRemove, onChangeDuration, onToggleLock }) {
  return (
    <div className={`timeline-item ${isManaging ? 'managing' : ''} ${isFocused ? 'focused' : ''} ${isEditing ? 'editing' : ''}`} data-stop-index={index} role="button" tabIndex="0" aria-label={`Focus ${stop.title} on the map`} onClick={() => onFocus(stop, index)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onFocus(stop, index); } }}>
      <div className="timeline-time">{stop.time}</div>
      <div className="timeline-rail"><StopIcon type={stop.type} />{!isLast && <span className="rail-line" />}</div>
      <div className="timeline-copy"><strong>{stop.title}</strong>{stop.locked && !isManaging && <span className="timeline-focus-state locked-state"><Icon name="lock" size={10} />Locked</span>}{stop.closed_during_visit && <span className="timeline-focus-state closed-state">{stop.closes_at ? `Closes ${stop.closes_at}` : 'Closed on arrival'}</span>}{isFocused && <span className="timeline-focus-state" aria-live="polite">On map</span>}<span className="timeline-place">{stop.place}</span><span className="timeline-address">{stop.detail}</span>{isManaging && stop.type !== 'stay' && stop.place_id && <StopControls stop={stop} index={index} onChangeDuration={onChangeDuration} onToggleLock={onToggleLock} />}</div>
      <span className="stop-duration">{stop.duration === 'overnight' ? 'overnight' : `${stop.duration} stop`}</span>
      <div className="timeline-actions">
        {isManaging && stop.type !== 'stay' && <button className="timeline-remove" title={`Remove ${stop.title}`} onClick={(event) => { event.stopPropagation(); onRemove(index); }}><Icon name="close" size={12} />Remove</button>}
        {(!isManaging || stop.type === 'stay') && <span className="timeline-action-placeholder" aria-hidden="true" />}
        <button className="timeline-change" title={`Choose a replacement for ${stop.title}`} onClick={(event) => { event.stopPropagation(); onChange(index); }}>{isEditing ? 'Choosing' : 'Change'}</button>
      </div>
    </div>
  );
}

// Add any place: search Google, and the backend places it along the route; or take the next suggestion.
export function AddStopPanel({ onAddPlace, onAddSuggestion }) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [isAdding, setIsAdding] = useState(false);
  if (!isOpen) return <button className="add-stop" onClick={() => setIsOpen(true)}><Icon name="plus" size={15} />Add a stop</button>;
  async function pick(text, suggestion) {
    setQuery(text);
    if (!suggestion) return;
    setIsAdding(true);
    const added = await onAddPlace(suggestion);
    setIsAdding(false);
    if (added) { setQuery(''); setIsOpen(false); }
  }
  return (
    <div className="add-stop-panel" aria-busy={isAdding}>
      <LocationField label="ADD ANY PLACE" value={query} onChange={(text, suggestion) => { void pick(text, suggestion); }} icon="end" resolveDetails={false} />
      <div className="add-stop-actions">
        <button type="button" className="add-stop-link" onClick={() => { onAddSuggestion(); setIsOpen(false); }}>Add the next suggestion instead</button>
        <button type="button" className="add-stop-link" onClick={() => { setQuery(''); setIsOpen(false); }}>Cancel</button>
      </div>
    </div>
  );
}

export function CandidateRow({ candidate, selected, actionLabel, actionTitle, onSelect, onShowOnMap }) {
  const category = candidate.category?.toLowerCase() || '';
  const icon = category.includes('restaurant') ? 'sun' : category.includes('gas') || category.includes('fuel') || category.includes('convenience') || category.includes('store') ? 'fuel' : 'sparkles';
  const isReplacementAction = actionLabel === 'Use' || actionLabel === 'Use here' || actionLabel === 'Replace';
  const resolvedActionLabel = isReplacementAction ? 'Replace' : actionLabel;
  const resolvedActionTitle = actionTitle || (isReplacementAction ? `Replace the selected timeline stop with ${candidate.name}` : actionLabel);
  return (
    <div className={`candidate-row ${selected ? 'selected' : ''}`} title={candidate.review_quote || candidate.reason}>
      <div className="candidate-icon"><Icon name={icon} size={15} /></div>
      <div className="candidate-copy">
        <strong>{candidate.name}</strong><span>{candidate.category} <i>·</i> {candidate.address}</span>
        <small className="candidate-scope">{candidate.recommendation_scope === 'destination' ? 'At destination' : isReplacementAction ? 'Replaces the selected timeline stop' : candidate.recommendation_kind === 'scenic' ? 'Scenic along route' : 'Practical along route'}</small>
        <small><span className="rating-star">★</span> {Number(candidate.rating || 0).toFixed(1)} ({Number(candidate.review_count || 0).toLocaleString()}) <i>·</i> {candidate.detour_minutes} min detour</small>
        <small className="candidate-cost">{candidate.cost_label || candidate.price_label || 'Cost to verify'} {candidate.website_uri && <a href={candidate.website_uri} target="_blank" rel="noreferrer">Official site ↗</a>}</small>
        {candidate.review_quote && <small className="review-preview">“{candidate.review_quote}”</small>}
      </div>
      <div className="candidate-score"><strong>{candidate.enjoyment_score}</strong><small>enjoyment</small></div>
      {onShowOnMap ? (
        <div className="candidate-actions">
          <button className="candidate-use" type="button" title={resolvedActionTitle} aria-label={resolvedActionTitle} onClick={() => onSelect(candidate)}>{selected ? 'Added' : resolvedActionLabel}</button>
          <button className="candidate-map-link" type="button" aria-label={`Show ${candidate.name} on the map`} onClick={() => onShowOnMap(candidate)}>Show on map</button>
        </div>
      ) : <button className="candidate-use" type="button" title={resolvedActionTitle} aria-label={resolvedActionTitle} onClick={() => onSelect(candidate)}>{selected ? 'Added' : resolvedActionLabel}</button>}
    </div>
  );
}
