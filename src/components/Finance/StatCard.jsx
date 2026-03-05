// ─── components/Finance/StatCard.jsx ─────────────────────────────────────────
import { memo } from "react";
import s from "./Finance.module.css";

const CHANGE_META = {
  up:      { cls: s.changeUp,      icon: "↗" },
  down:    { cls: s.changeDown,    icon: "↙" },
  neutral: { cls: s.changeNeutral, icon: "↘" },
};

export const SkeletonStatCard = () => (
  <div className={s.statCard}>
    <div className={s.skeleton} style={{ width: 40, height: 40, borderRadius: 10 }} />
    <div className={s.skeleton} style={{ width: "60%", height: 12, marginTop: 8 }} />
    <div className={s.skeleton} style={{ width: "80%", height: 22 }} />
    <div className={s.skeleton} style={{ width: "40%", height: 12 }} />
  </div>
);

const StatCard = memo(({ icon, label, value, change, changeType = "neutral" }) => {
  const { cls, icon: arrow } = CHANGE_META[changeType] ?? CHANGE_META.neutral;
  return (
    <article className={s.statCard} aria-label={label}>
      <div className={s.statIcon} aria-hidden="true">{icon}</div>
      <p className={s.statLabel}>{label}</p>
      <p className={s.statValue}>{value}</p>
      <p className={`${s.statChange} ${cls}`}>
        <span aria-hidden="true">{arrow}</span> {change}
      </p>
    </article>
  );
});

StatCard.displayName = "StatCard";
export default StatCard;