import Icon from './Icon';

function StopIcon({ type }) {
  return <span className={`stop-icon stop-${type}`}><Icon name={type === 'fuel' ? 'fuel' : type === 'stay' ? 'suitcase' : type === 'lunch' ? 'sun' : 'compass'} size={16} /></span>;
}

export function TimelineRow({ stop, index, isLast, isFocused, isEditing, isManaging, onFocus, onChange, onRemove }) {
  return (
    <div className={`timeline-item ${isManaging ? 'managing' : ''} ${isFocused ? 'focused' : ''} ${isEditing ? 'editing' : ''}`} data-stop-index={index} role="button" tabIndex="0" aria-label={`Focus ${stop.title} on the map`} onClick={() => onFocus(stop, index)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onFocus(stop, index); } }}>
      <div className="timeline-time">{stop.time}</div>
      <div className="timeline-rail"><StopIcon type={stop.type} />{!isLast && <span className="rail-line" />}</div>
      <div className="timeline-copy"><strong>{stop.title}</strong>{isFocused && <span className="timeline-focus-state" aria-live="polite">On map</span>}<span className="timeline-place">{stop.place}</span><span className="timeline-address">{stop.detail}</span></div>
      <span className="stop-duration">{stop.duration === 'overnight' ? 'overnight' : `${stop.duration} stop`}</span>
      <div className="timeline-actions">
        {isManaging && stop.type !== 'stay' && <button className="timeline-remove" title={`Remove ${stop.title}`} onClick={(event) => { event.stopPropagation(); onRemove(index); }}><Icon name="close" size={12} />Remove</button>}
        {(!isManaging || stop.type === 'stay') && <span className="timeline-action-placeholder" aria-hidden="true" />}
        <button className="timeline-change" title={`Choose a replacement for ${stop.title}`} onClick={(event) => { event.stopPropagation(); onChange(index); }}>{isEditing ? 'Choosing' : 'Change'}</button>
      </div>
    </div>
  );
}

export function CandidateRow({ candidate, selected, actionLabel, actionTitle, onSelect }) {
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
      <button className="candidate-use" type="button" title={resolvedActionTitle} aria-label={resolvedActionTitle} onClick={() => onSelect(candidate)}>{selected ? 'Added' : resolvedActionLabel}</button>
    </div>
  );
}
