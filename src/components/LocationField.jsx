import { useEffect, useRef, useState } from 'react';
import Icon from './Icon';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function LocationField({ label, value, onChange, icon }) {
  const fieldRef = useRef(null);
  const [suggestions, setSuggestions] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isFocused, setIsFocused] = useState(false);

  useEffect(() => {
    const query = value.trim();
    if (query.length < 2) { setSuggestions([]); return undefined; }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setIsSearching(true);
      try {
        const response = await fetch(`${API_URL}/places/autocomplete?q=${encodeURIComponent(query)}`, { signal: controller.signal });
        if (!response.ok) throw new Error('Autocomplete unavailable');
        const result = await response.json();
        setSuggestions(result.suggestions || []);
      } catch (error) { if (error.name !== 'AbortError') setSuggestions([]); }
      finally { setIsSearching(false); }
    }, 240);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [value]);

  return (
    <div ref={fieldRef} className="location-field-wrap" onBlur={(event) => { if (!fieldRef.current?.contains(event.relatedTarget)) { setIsFocused(false); setSuggestions([]); } }}>
      <label className="location-field"><span className="field-label">{label}</span><span className="field-row"><span className={`location-dot ${icon}`} /> <input aria-label={label} value={value} onFocus={() => setIsFocused(true)} onChange={(event) => onChange(event.target.value)} /></span></label>
      {isFocused && (isSearching || suggestions.length > 0) && <div className="location-suggestions" role="listbox" aria-label={`${label} suggestions`}>
        {isSearching && <div className="location-suggestion muted">Searching cities…</div>}
        {suggestions.map((suggestion) => <button className="location-suggestion" type="button" role="option" key={suggestion.id} onMouseDown={(event) => event.preventDefault()} onClick={() => { onChange(suggestion.text); setSuggestions([]); }}><strong>{suggestion.main_text}</strong><span>{suggestion.secondary_text}</span></button>)}
      </div>}
    </div>
  );
}
