// ─── components/Finance/StatCard.jsx ─────────────────────────────────────────
import { memo } from "react";
import {
  WalletCards,
  TrendingUp,
  ReceiptText,
  Clock3,
  AlertTriangle,
  Banknote,
  BarChart3,
  CircleDollarSign,
} from "lucide-react";
import s from "./Finance.module.css";

const CHANGE_META = {
  up: { cls: s.changeUp, icon: "↗" },
  down: { cls: s.changeDown, icon: "↙" },
  neutral: { cls: s.changeNeutral, icon: "↘" },
};

const ICONS = {
  revenue: WalletCards,
  totalRevenue: WalletCards,
  profit: TrendingUp,
  netProfit: TrendingUp,
  invoices: ReceiptText,
  outstanding: Clock3,
  overdue: AlertTriangle,
  expenses: Banknote,
  cashflow: BarChart3,
  cashFlow: BarChart3,
};

const getIconComponent = (id) => {
  return ICONS[id] || CircleDollarSign;
};

const isFeaturedCard = (id) => {
  return id === "profit" || id === "netProfit";
};

export const SkeletonStatCard = () => (
  <div className={s.statCard}>
    <div className={s.statCardHeader}>
      <div className={`${s.statIconBadge} ${s.statIconSkeleton}`} />
      <div className={s.skeleton} style={{ width: "55%", height: 14 }} />
    </div>

    <div className={s.statMetrics}>
      <div className={s.skeleton} style={{ width: "70%", height: 26 }} />
      <div className={s.skeleton} style={{ width: "42%", height: 12 }} />
    </div>
  </div>
);

const StatCard = memo(({ id, label, value, change, changeType = "neutral" }) => {
  const { cls, icon: arrow } = CHANGE_META[changeType] ?? CHANGE_META.neutral;
  const featured = isFeaturedCard(id);
  const Icon = getIconComponent(id);

  return (
    <article className={s.statCard} aria-label={label}>
      <div className={s.statCardHeader}>
        <div
          className={`${s.statIconBadge} ${
            featured ? s.statIconBadgeActive : s.statIconBadgeNeutral
          }`}
          aria-hidden="true"
        >
          <Icon className={s.statIconSvg} strokeWidth={2.2} />
        </div>

        <p className={s.statLabel}>{label}</p>
      </div>

      <div className={s.statMetrics}>
        <p className={s.statValue}>{value}</p>

        <p className={`${s.statChange} ${cls}`}>
          <span aria-hidden="true">{arrow}</span> {change}
        </p>
      </div>
    </article>
  );
});

StatCard.displayName = "StatCard";

export default StatCard;