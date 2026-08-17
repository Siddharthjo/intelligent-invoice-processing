import { useState, type FormEvent } from "react";
import { login } from "./api";
import { LOGIN_EVENT } from "./events";

export function LoginApp() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const user = await login(username.trim(), password);
      setPassword("");
      window.dispatchEvent(new CustomEvent(LOGIN_EVENT, { detail: user }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <h2>Log in</h2>
      <form id="login-form" onSubmit={handleSubmit}>
        <div className="login-field">
          <label htmlFor="login-username">Username</label>
          <input
            id="login-username"
            type="text"
            autoComplete="username"
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </div>
        <div className="login-field">
          <label htmlFor="login-password">Password</label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        <button type="submit" className="btn-primary" disabled={submitting}>
          Log in
        </button>
        {error && <p className="error-text">{error}</p>}
      </form>
    </>
  );
}
