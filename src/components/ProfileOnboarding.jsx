import Icon from './Icon';

export default function ProfileOnboarding({ profile, userProfile, onComplete }) {
  const { profileSummary, profileBalance, profileOptions, preferences, adventureLevel, onTogglePreference, onAdventureInput } = profile;

  return <main className="onboarding-page">
    <section className="onboarding-card">
      <div className="brand auth-brand"><span className="brand-mark"><span /></span><span>vibetrip</span></div>
      <p className="eyebrow">FIRST-TIME SETUP</p>
      <h1>Make the route feel like yours.</h1>
      <p className="onboarding-copy">Hi {userProfile.name || 'traveller'} — tell us how you like to travel. These defaults help VibeTrip choose sensible stops, detours, and places to eat.</p>

      <section className="onboarding-profile-card">
        <div className="card-heading"><div><p className="eyebrow">TRAVEL PROFILE</p><h2>{profileSummary}</h2></div><span className="profile-helper">Used to shape your recommendations</span></div>
        <div className="profile-tags onboarding-tags">{profileOptions.map((option) => <button type="button" className={`profile-tag-button ${preferences.includes(option.id) ? 'active' : ''}`} key={option.id} onClick={() => onTogglePreference(option.id)}><Icon name={option.icon} size={14} />{option.label}</button>)}</div>
        <div className="profile-meter"><div className="meter-labels"><span>LAID BACK</span><span>ADVENTUROUS</span></div><input className="meter-input" type="range" min="0" max="100" step="1" value={adventureLevel} onInput={onAdventureInput} aria-label="Travel profile balance between laid back and adventurous" style={{ '--meter-level': `${adventureLevel}%` }} /><div className="meter-track" aria-hidden="true" /><div className="meter-caption" aria-live="polite"><span>{profileBalance}</span><strong>{adventureLevel}%</strong></div></div>
      </section>

      <button className="generate-button onboarding-submit" type="button" onClick={onComplete}>Continue to planner <Icon name="arrow" size={17} /></button>
      <p className="onboarding-note"><Icon name="check" size={13} />You can change these preferences any time from your account menu.</p>
    </section>
  </main>;
}
