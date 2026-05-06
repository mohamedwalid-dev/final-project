// ─── components/Finance/StatCard.jsx ─────────────────────────────────────────
import { memo } from "react";
import s from "./Finance.module.css";

const CHANGE_META = {
  up:      { cls: s.changeUp },
  down:    { cls: s.changeDown },
  neutral: { cls: s.changeNeutral },
};

export const SkeletonStatCard = () => (
  <div className={s.statCard}>
    <div className={s.skeleton} style={{ width: "60%", height: 12, marginTop: 8 }} />
    <div className={s.skeleton} style={{ width: "80%", height: 22 }} />
    <div className={s.skeleton} style={{ width: "40%", height: 12 }} />
  </div>
);

const StatCard = memo(({ label, value, change, changeType = "neutral" }) => {
  const { cls } = CHANGE_META[changeType] ?? CHANGE_META.neutral;

  return (
    <article className={s.statCard} aria-label={label}>
      
  

      <p className={s.statLabel}>{label}</p>
      <p className={s.statValue}>{value}</p>

      <p className={`${s.statChange} ${cls}`}>
        {change}
      </p>

    </article>
  );
});

StatCard.displayName = "StatCard";
export default StatCard;