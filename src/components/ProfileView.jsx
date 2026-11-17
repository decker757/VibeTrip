import Icon from './Icon';
import { getInitials } from '../app/formatters';

export default function ProfileView({
  profile,
  userProfile,
  onUpdateProfile,
  onSaveProfile,
  onGoPlan,
  learnedSignals = [],
  onDismissSignal,
}) {
  const { profileSummary, profileBalance, profileOptions, preferences, adventureLevel, onTogglePreference, onAdventureInput } = profile;

  return (
    <div className="profile-page">
      <div className="collection-heading profile-page-heading">
        <div>
          <p className="eyebrow">YOUR PROFILE</p>
          <h1>Travel, your way.</h1>
          <p>Keep the identity details lightweight. VibeTrip only needs enough context to make better recommendations for an exchange road trip.</p>
        </div>
        <button className="primary-inline-action" type="button" onClick={onGoPlan}><Icon name="compass" size={14} />Plan a trip</button>
      </div>

      <div className="profile-page-grid">
        <section className="account-card">
          <div className="profile-avatar-large">{getInitials(userProfile.name)}</div>
          <div>
            <p className="eyebrow">ACCOUNT</p>
            <h2>Exchange student</h2>
            <p className="account-copy">Your name and home base help personalize every route you plan.</p>
          </div>
          <label className="profile-field"><span>Display name</span><input value={userProfile.name} onChange={(event) => onUpdateProfile('name', event.target.value)} onBlur={onSaveProfile} /></label>
          <label className="profile-field"><span>Home base</span><input value={userProfile.home} onChange={(event) => onUpdateProfile('home', event.target.value)} onBlur={onSaveProfile} /></label>
          <p className="profile-note"><Icon name="check" size={13} />Changes save automatically and guide the agents when you plan a trip.</p>
        </section>

        <section className="profile-card profile-settings-card">
          <div className="card-heading"><div><p className="eyebrow">TRAVEL PROFILE</p><h2>{profileSummary}</h2></div><span className="profile-helper">Your saved planning defaults</span></div>
          <p className="account-copy">These defaults seed every new route. Fine-tune them for a specific journey from the planner without changing your account profile.</p>
          <div className="profile-tags profile-page-tags">{profileOptions.map((option) => <button type="button" className={`profile-tag-button ${preferences.includes(option.id) ? 'active' : ''}`} key={option.id} onClick={() => onTogglePreference(option.id)}><Icon name={option.icon} size={14} />{option.label}</button>)}</div>
          <div className="profile-meter profile-page-meter"><div className="meter-labels"><span>LAID BACK</span><span>ADVENTUROUS</span></div><input className="meter-input" type="range" min="0" max="100" step="1" value={adventureLevel} onInput={onAdventureInput} aria-label="Travel profile balance between laid back and adventurous" style={{ '--meter-level': `${adventureLevel}%` }} /><div className="meter-track" aria-hidden="true" /><div className="meter-caption" aria-live="polite"><span>{profileBalance}</span><strong>{adventureLevel}%</strong></div></div>
        </section>
      </div>

      <LearnedSignalsCard signals={learnedSignals} onDismiss={onDismissSignal} />

      <section className="profile-privacy-card"><Icon name="bookmark" size={17} /><div><h2>Your trips stay yours first.</h2><p>New trips are private drafts. After the road trip, mark one completed, add memories, and publish it to Explore when you are comfortable sharing.</p></div></section>
    </div>
  );
}

const SOURCE_LABELS = {
  profile: 'From your profile',
  behaviour: 'Learned from your trips',
  both: 'Profile + trips',
};

function LearnedSignalsCard({ signals, onDismiss }) {
  return (
    <section className="profile-card learned-signals-card">
      <div className="card-heading"><div><p className="eyebrow">AGENT MEMORY</p><h2>What VibeTrip has learned about you</h2></div></div>
      {signals.length === 0 ? (
        <p className="account-copy">Nothing learned yet. Plan a few trips and swap some stops.</p>
      ) : (
        <ul className="learned-signal-list">
          {signals.map((item) => (
            <li className="learned-signal" key={item.signal}>
              <span className="learned-signal-label">{item.label}</span>
              <span className="learned-signal-source">{SOURCE_LABELS[item.source] || SOURCE_LABELS.profile}</span>
              {item.evidence_count > 0 && <small>based on {item.evidence_count} {item.evidence_count === 1 ? 'action' : 'actions'}</small>}
              {item.source === 'behaviour' && onDismiss && <button type="button" className="learned-signal-dismiss" onClick={() => onDismiss(item.signal)}>Not me</button>}
              {item.source === 'both' && <small className="learned-signal-hint">Remove it from your preferences above to turn it off</small>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
