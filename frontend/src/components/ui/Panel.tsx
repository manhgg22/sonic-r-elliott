import { formatNumber, formatUsdPrice } from "../../shared/format";


type PanelProps = {
  title: string;
  meta?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
};

export function Panel({ title, meta, icon, children, className = "" }: PanelProps) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel-heading">
        <div className="panel-title">
          {icon}
          <h2>{title}</h2>
        </div>
        {meta && <span>{meta}</span>}
      </header>
      {children}
    </section>
  );
}

export function Kpi({ label, value, tone = "", note }: {
  label: string;
  value: string;
  tone?: string;
  note?: string;
}) {
  return (
    <div className="kpi">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
      {note && <small>{note}</small>}
    </div>
  );
}

export function Level({ label, value, tone = "", currency = false }: {
  label: string;
  value: unknown;
  tone?: string;
  currency?: boolean;
}) {
  return (
    <div className="level">
      <span>{label}</span>
      <b className={tone}>
        {currency ? formatUsdPrice(value) : formatNumber(value)}
      </b>
    </div>
  );
}
