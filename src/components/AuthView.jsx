import { useState } from 'react';
import Icon from './Icon';
import { PLANNER_API_URL } from '../app/plannerData';

export default function AuthView({ onAuthenticated, onDemoMode }) {
  const [isSignup, setIsSignup] = useState(false);
  const [email, setEmail] = useState('demo@vibetrip.local');
  const [password, setPassword] = useState('vibetrip-demo');
  const [displayName, setDisplayName] = useState('');
  const [homeBase, setHomeBase] = useState('Singapore');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  async function submit(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError('');
    try {
      const response = await fetch(`${PLANNER_API_URL}/auth/${isSignup ? 'signup' : 'login'}`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, display_name: displayName, home_base: homeBase }),
      });
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(result.detail || 'Authentication failed.');
      }
      const result = await response.json();
      onAuthenticated(result.user);
    } catch (requestError) {
      setError(requestError.message || 'Could not reach the local API.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return <main className="auth-page"><section className="auth-card"><div className="brand auth-brand"><span className="brand-mark"><span /></span><span>vibetrip</span></div><p className="eyebrow">PRIVATE TRAVEL WORKSPACE</p><h1>{isSignup ? 'Create your travel profile.' : 'Welcome back.'}</h1><p className="auth-copy">Your trips and OKF profile context stay separated from everyone else’s. This local login needs no hosted auth setup.</p><form className="auth-form" onSubmit={submit}>{isSignup && <><label>Display name<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} required /></label><label>Home base<input value={homeBase} onChange={(event) => setHomeBase(event.target.value)} required /></label></>}<label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength="8" required /></label>{error && <p className="auth-error" role="alert">{error}</p>}<button className="generate-button auth-submit" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Signing in…' : isSignup ? 'Create account' : 'Sign in'}<Icon name="arrow" size={17} /></button></form><div className="auth-actions"><button className="text-action" type="button" onClick={() => { setIsSignup((value) => !value); setError(''); }}>{isSignup ? 'Already have an account? Sign in' : 'Create a new account'}</button><button className="secondary-action" type="button" onClick={onDemoMode}><Icon name="sparkles" size={13} />Continue in demo mode</button></div><p className="auth-demo-note">Demo login: <strong>demo@vibetrip.local</strong> / <strong>vibetrip-demo</strong></p></section></main>;
}
