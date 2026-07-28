import { FormEvent, useState } from "react";
import { Activity, LockKeyhole, ShieldCheck, UserRound } from "lucide-react";
import { Button, Input } from "antd";
import { login, type AuthSession } from "../../services/api";


export function LoginPage({ onAuthenticated }: {
  onAuthenticated: (session: AuthSession) => void;
}) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const session = await login(username.trim(), password);
      onAuthenticated(session);
    } catch (loginError) {
      setError((loginError as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="login-shell">
      <section className="login-panel">
        <div className="login-brand">
          <span className="login-mark"><i /><i /><i /></span>
          <div><b>SONIC R</b><small>MARKET INTELLIGENCE</small></div>
        </div>
        <div className="login-copy">
          <span className="login-kicker"><Activity /> PRIVATE TERMINAL</span>
          <h1>Đăng nhập hệ thống</h1>
          <p>Không gian phân tích và paper trading dành riêng cho operator.</p>
        </div>
        <form onSubmit={submit}>
          <label htmlFor="sonic-username">Tên đăng nhập</label>
          <Input
            id="sonic-username"
            size="large"
            prefix={<UserRound />}
            value={username}
            autoComplete="username"
            onChange={(event) => setUsername(event.target.value)}
            disabled={submitting}
          />
          <label htmlFor="sonic-password">Mật khẩu</label>
          <Input.Password
            id="sonic-password"
            size="large"
            prefix={<LockKeyhole />}
            value={password}
            autoComplete="current-password"
            onChange={(event) => setPassword(event.target.value)}
            disabled={submitting}
            autoFocus
          />
          {error && <div className="login-error" role="alert">{error}</div>}
          <Button
            type="primary"
            htmlType="submit"
            size="large"
            loading={submitting}
            disabled={!username.trim() || !password}
          >
            ĐĂNG NHẬP
          </Button>
        </form>
        <footer><ShieldCheck /> Phiên đăng nhập được bảo vệ bằng cookie HttpOnly</footer>
      </section>
      <aside className="login-visual" aria-hidden="true">
        <div className="login-orbit orbit-one" />
        <div className="login-orbit orbit-two" />
        <div className="login-radar"><span /><span /><span /></div>
        <p>REALTIME MARKET<br /><b>DECISION SUPPORT</b></p>
      </aside>
    </main>
  );
}
