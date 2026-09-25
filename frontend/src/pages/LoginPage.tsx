import { type FormEvent, useState } from 'react';

import { ApiError, apiClient } from '../api/apiClient';
import { AmbientBackground } from '../components/AmbientBackground';
import { LogoMark } from '../components/LogoMark';

/** Props for LoginPage. */
interface LoginPageProps {
  onLoggedIn: () => void;
}

/**
 * The password form shown to a logged-out browser, over the 3D backdrop.
 * @param props Called after a successful login.
 * @returns The login page.
 */
export function LoginPage(props: LoginPageProps) {
  const { onLoggedIn } = props;
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      await apiClient.logIn(password);
      onLoggedIn();
    } catch (caught: unknown) {
      if (caught instanceof ApiError) {
        setError(caught.message);
      } else {
        setError('The server could not be reached.');
      }
      setSubmitting(false);
    }
  };

  return (
    <>
      <AmbientBackground pulseKey="login" />
      <div className="login">
        <div className="card login-card">
          <LogoMark size={48} />
          <h1>Instruments Explorer</h1>
          <p className="muted">Every instrument in the unified broker interface, in one place.</p>
          <form className="login-form" onSubmit={submit}>
            <label>
              Password
              <input
                className="input"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoFocus
                required
              />
            </label>
            <p className="login-error" role="alert">
              {error}
            </p>
            <button type="submit" className="button button-primary" disabled={submitting || password === ''}>
              {submitting ? 'Logging in…' : 'Log in'}
            </button>
          </form>
        </div>
      </div>
    </>
  );
}
