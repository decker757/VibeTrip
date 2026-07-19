import { useEffect, useRef, useState } from 'react';
import Icon from './Icon';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const AUTOCOMPLETE_MIN_LENGTH = 3;
const AUTOCOMPLETE_DELAY_MS = 600;

function createSessionToken() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function LocationField({ label, value, onChange, icon, selectedLocation }) {
  const fieldRef = useRef(null);
  const sessionTokenRef = useRef(null);
  const [suggestions, setSuggestions] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isResolving, setIsResolving] = useState(false);
  const [isFocused, setIsFocused] = useState(false);

  useEffect(() => {
    if (selectedLocation) { setSuggestions([]); setIsSearching(false); return undefined; }
    const query = value.trim();
    if (query.length < AUTOCOMPLETE_MIN_LENGTH) { setSuggestions([]); return undefined; }
    if (!sessionTokenRef.current) sessionTokenRef.current = createSessionToken();
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setIsSearching(true);
      try {
        const params = new URLSearchParams({ q: query, session_token: sessionTokenRef.current });
        const response = await fetch(`${API_URL}/places/autocomplete?${params.toString()}`, { signal: controller.signal });
        if (!response.ok) throw new Error('Autocomplete unavailable');
        const result = await response.json();
        setSuggestions(result.suggestions || []);
      } catch (error) { if (error.name !== 'AbortError') setSuggestions([]); }
      finally { setIsSearching(false); }
    }, AUTOCOMPLETE_DELAY_MS);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [value, selectedLocation]);

  const displayValue = selectedLocation?.main_text || value;

  async function selectSuggestion(suggestion) {
    setIsResolving(true);
    let resolvedSuggestion = suggestion;
    const sessionToken = sessionTokenRef.current;
    try {
      const params = new URLSearchParams({ place_id: suggestion.id });
      if (sessionToken) params.set('session_token', sessionToken);
      const response = await fetch(`${API_URL}/places/details?${params.toString()}`);
      if (response.ok) {
        const result = await response.json();
        if (result.place) resolvedSuggestion = { ...suggestion, ...result.place };
      }
    } catch {
      // Autocomplete remains a usable fallback if details lookup is unavailable.
    } finally {
      setIsResolving(false);
    }
    sessionTokenRef.current = null;
    onChange(resolvedSuggestion.text, resolvedSuggestion);
    setSuggestions([]);
    setIsFocused(false);
  }

  return (
    <div ref={fieldRef} className="location-field-wrap" onBlur={(event) => { if (!fieldRef.current?.contains(event.relatedTarget)) { setIsFocused(false); setSuggestions([]); sessionTokenRef.current = null; } }}>
      <label className="location-field"><span className="field-label">{label}</span><span className="field-row"><span className={`location-dot ${icon}`} /> <input aria-label={label} aria-busy={isResolving} value={displayValue} onFocus={() => { setIsFocused(true); if (!sessionTokenRef.current) sessionTokenRef.current = createSessionToken(); }} onChange={(event) => onChange(event.target.value, null)} /></span>{selectedLocation?.secondary_text && <span className="location-selected-detail">{selectedLocation.secondary_text}</span>}</label>
      {isFocused && (isSearching || isResolving || suggestions.length > 0) && <div className="location-suggestions" role="listbox" aria-label={`${label} suggestions`}>
        {(isSearching || isResolving) && <div className="location-suggestion muted">{isResolving ? 'Finding exact address…' : 'Searching places…'}</div>}
        {suggestions.map((suggestion) => <button className="location-suggestion" type="button" role="option" key={suggestion.id} onMouseDown={(event) => event.preventDefault()} onClick={() => { void selectSuggestion(suggestion); }}><strong>{suggestion.main_text}</strong><span>{suggestion.secondary_text}</span></button>)}
      </div>}
    </div>
  );
}
