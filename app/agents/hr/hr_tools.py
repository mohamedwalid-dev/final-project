"""
🔧 HR Agent LangChain Tools — v4.0 Production
===============================================
File: app/agents/hr/hr_tools.py

ℹ️ NODE.JS / DB NOTE:
    This file has no MongoDB/Motor dependency and makes no HTTP calls to
    the Node.js API. Every @tool function here is pure logic — it takes
    typed arguments (numbers, strings, bools) and returns a plain string
    verdict computed locally. Nothing imports core.node_hr_proxy or
    core.node_api_client. There is nothing here to repoint for the
    Node.js migration — left otherwise identical to v4.0.

Tools Coverage:
    ✅ Leave Policy Check
    ✅ Team Risk Assessment
    ✅ Performance Context Evaluation
    ✅ Salary Review Validation        (NEW)
    ✅ Incentive Eligibility Check     (NEW)
    ✅ Absence Pattern Analysis        (NEW)
    ✅ Attendance KPI Evaluator        (NEW)
    ✅ Egyptian Labor Law Checker      (NEW)
    ✅ Budget Compliance Guard         (NEW)
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# 🏖️  LEAVE TOOLS
# ════════════════════════════════════════════════════════════════════════════

@tool
def check_leave_policy(requested_days: int, leave_balance: int, leave_type: str = "annual") -> str:
    """
    Check if a leave request complies with Egyptian Labor Law and company HR policy.
    Returns a structured policy compliance verdict.

    Args:
        requested_days: Number of days requested.
        leave_balance: Employee's current leave balance.
        leave_type: Type of leave (annual | sick | emergency | unpaid).
    """
    issues: list[str] = []
    notes:  list[str] = []

    if leave_balance <= 0:
        return (
            "POLICY_VIOLATION: Employee has zero leave balance. "
            "Per Egyptian Labor Law Art. 47, no leave can be granted without balance. "
            "Decision: REJECT."
        )

    if requested_days <= 0:
        return "POLICY_VIOLATION: Requested days must be greater than zero. Decision: REJECT."

    if requested_days > leave_balance:
        issues.append(
            f"Requested {requested_days}d exceeds available balance of {leave_balance}d. "
            "Decision: REJECT."
        )

    if requested_days > 21 and leave_type == "annual":
        notes.append(
            "Annual leave > 21 days: Egyptian Labor Law mandates employer consent. "
            "Flag for Director review."
        )

    if requested_days > 14:
        notes.append(
            "Requests over 14 consecutive days require secondary HR approval flag."
        )

    if leave_type == "sick" and requested_days > 2:
        notes.append(
            "Sick leave > 2 days requires a valid medical certificate (Egyptian Law Art. 54)."
        )

    if leave_type == "emergency" and requested_days > 7:
        issues.append(
            "Emergency leave is capped at 7 days/year by Egyptian Labor Law. "
            "Excess days must be charged against annual balance."
        )

    if issues:
        return "POLICY_VIOLATION: " + " | ".join(issues)

    ratio = leave_balance / max(requested_days, 1)
    status = "excellent" if ratio >= 3 else "adequate" if ratio >= 1.5 else "tight"

    result = f"POLICY_OK: Request complies with policy. Balance ratio={ratio:.1f}x ({status})."
    if notes:
        result += " Notes: " + " | ".join(notes)
    return result


@tool
def assess_team_risk(team_workload: str, attendance_rate: float, department: str = "General") -> str:
    """
    Assess the operational risk of approving leave given current team workload
    and the employee's attendance history.

    Args:
        team_workload: Current team workload level (low | medium | high | critical).
        attendance_rate: Employee's attendance rate as a decimal (e.g., 0.92 = 92%).
        department: Employee's department name.
    """
    risk_notes: list[str] = []
    risk_level = "low"

    workload_lower = team_workload.lower().strip()

    if workload_lower == "critical":
        risk_notes.append(
            f"CRITICAL workload in {department} — leave approval will severely impact operations. "
            "Strong recommendation: defer or escalate."
        )
        risk_level = "critical"
    elif workload_lower == "high":
        risk_notes.append(
            f"HIGH workload in {department} — absence will add pressure on the team. "
            "Recommend approval only if coverage is arranged."
        )
        risk_level = "high"
    elif workload_lower == "medium":
        risk_notes.append(f"MEDIUM workload in {department} — manageable if planned properly.")
        risk_level = "medium"
    else:
        risk_notes.append(f"LOW workload in {department} — minimal operational impact.")

    if attendance_rate < 0.70:
        risk_notes.append(
            f"⚠️ Attendance rate {attendance_rate:.0%} is critically low (threshold: 70%). "
            "This is a serious concern — consider counseling before approval."
        )
        risk_level = "high" if risk_level not in ("critical",) else risk_level
    elif attendance_rate < 0.85:
        risk_notes.append(
            f"⚠️ Attendance rate {attendance_rate:.0%} is below the 85% threshold. Monitor closely."
        )
    elif attendance_rate >= 0.95:
        risk_notes.append(
            f"✅ Excellent attendance record ({attendance_rate:.0%}). Positive factor."
        )

    return f"RISK_LEVEL={risk_level.upper()} | " + " | ".join(risk_notes)


@tool
def evaluate_performance_context(
    performance_score: float,
    requested_days: int,
    absence_count: int = 0,
    overtime_hours: int = 0,
) -> str:
    """
    Evaluate whether the employee's overall performance context justifies the leave request.

    Args:
        performance_score: Performance appraisal score as decimal (e.g., 0.85 = 85%).
        requested_days: Number of days being requested.
        absence_count: YTD absence count.
        overtime_hours: YTD overtime hours worked.
    """
    factors: list[str] = []

    # Performance score
    if performance_score >= 0.90:
        factors.append(
            f"TOP PERFORMER ({performance_score:.0%}): "
            "Exceptional contributor — leave should be strongly supported."
        )
    elif performance_score >= 0.75:
        factors.append(
            f"SOLID PERFORMER ({performance_score:.0%}): "
            "Meets expectations — standard leave approval is appropriate."
        )
    elif performance_score >= 0.55:
        factors.append(
            f"AVERAGE PERFORMER ({performance_score:.0%}): "
            "Performance is acceptable but warrants attention."
        )
    elif performance_score >= 0.40:
        factors.append(
            f"BELOW AVERAGE ({performance_score:.0%}): "
            f"Performance is a concern — {requested_days}d leave should be reviewed carefully."
        )
    else:
        factors.append(
            f"LOW PERFORMER ({performance_score:.0%}): "
            "Critically low performance — leave may not be appropriate at this stage. "
            "Consider PIP first."
        )

    # Absence history
    if absence_count == 0:
        factors.append("✅ Perfect attendance record YTD.")
    elif absence_count <= 3:
        factors.append(f"✅ Low absence count ({absence_count} YTD) — within acceptable range.")
    elif absence_count <= 8:
        factors.append(f"⚠️ Moderate absences ({absence_count} YTD) — monitor trend.")
    else:
        factors.append(
            f"🚫 High absence count ({absence_count} YTD) — "
            "combined with leave request this warrants escalation."
        )

    # Overtime
    if overtime_hours >= 60:
        factors.append(
            f"✅ High overtime contribution ({overtime_hours}h YTD) — "
            "employee has invested extra effort. Supports leave approval."
        )
    elif overtime_hours >= 20:
        factors.append(f"ℹ️ Moderate overtime ({overtime_hours}h YTD).")

    return " | ".join(factors)


# ════════════════════════════════════════════════════════════════════════════
# 💰  SALARY TOOLS
# ════════════════════════════════════════════════════════════════════════════

@tool
def validate_salary_increment(
    current_salary_egp: float,
    requested_increment_pct: float,
    months_since_last_increment: int,
    is_on_pip: bool = False,
    is_on_probation: bool = False,
    budget_utilization: float = 0.80,
) -> str:
    """
    Validate a salary increment request against company policy and Egyptian Labor Law.

    Args:
        current_salary_egp: Current gross salary in EGP.
        requested_increment_pct: Requested increment as decimal (e.g., 0.15 = 15%).
        months_since_last_increment: Months elapsed since last salary change.
        is_on_pip: Whether employee is on a Performance Improvement Plan.
        is_on_probation: Whether employee is in probation period (< 6 months).
        budget_utilization: Current dept budget utilization (0.0–1.0).
    """
    issues:  list[str] = []
    factors: list[str] = []

    # Hard blocks
    if is_on_probation:
        return (
            "BLOCKED: Employee is on probation. "
            "Salary increments are not permitted during probation period (< 6 months). "
            "Decision: DEFER."
        )

    if is_on_pip:
        return (
            "BLOCKED: Employee is on a Performance Improvement Plan (PIP). "
            "Salary increments are suspended until PIP completion and successful review. "
            "Decision: DEFER."
        )

    if budget_utilization > 0.95:
        return (
            f"BLOCKED: Department budget utilization is at {budget_utilization:.0%} "
            "(threshold: 95%). No increment budget available. Decision: DEFER."
        )

    # Policy checks
    if months_since_last_increment < 12:
        issues.append(
            f"Last increment was only {months_since_last_increment} months ago "
            "(policy minimum: 12 months). Early increment requires Director approval."
        )

    if requested_increment_pct > 0.30:
        issues.append(
            f"Requested increment ({requested_increment_pct:.0%}) exceeds 30% cap. "
            "Requires escalation to Director/CEO regardless of other factors."
        )

    if requested_increment_pct > 0.20:
        factors.append(
            f"Note: increment > 20% ({requested_increment_pct:.0%}) requires HR Director sign-off."
        )

    new_salary = current_salary_egp * (1 + requested_increment_pct)
    factors.append(
        f"New salary would be {new_salary:,.0f} EGP "
        f"(+{requested_increment_pct:.0%} from {current_salary_egp:,.0f} EGP)."
    )

    if months_since_last_increment >= 24:
        factors.append(
            f"✅ Employee has waited {months_since_last_increment} months since last increment "
            "— strong justification for review."
        )

    if issues:
        return "POLICY_CAUTION: " + " | ".join(issues + factors)
    return "POLICY_OK: " + " | ".join(factors) if factors else "POLICY_OK: Increment complies with policy."


@tool
def check_market_benchmark(
    current_salary_egp: float,
    market_median_egp: float,
    job_level: str,
    salary_grade: str,
) -> str:
    """
    Compare employee's salary against market benchmark to assess competitiveness.

    Args:
        current_salary_egp: Current gross salary in EGP.
        market_median_egp: Market median salary for same role/level in EGP.
        job_level: Employee's job level (junior | senior | lead | manager).
        salary_grade: Employee's salary grade (A–E).
    """
    if market_median_egp <= 0:
        return "BENCHMARK_UNKNOWN: No market data available for comparison."

    gap_pct = (market_median_egp - current_salary_egp) / market_median_egp

    if gap_pct > 0.25:
        return (
            f"BELOW_MARKET_CRITICAL: Employee is {gap_pct:.0%} below market median "
            f"({current_salary_egp:,.0f} vs {market_median_egp:,.0f} EGP) for "
            f"{job_level}/{salary_grade}. High attrition risk — increment strongly recommended."
        )
    elif gap_pct > 0.10:
        return (
            f"BELOW_MARKET: Employee is {gap_pct:.0%} below market median. "
            f"Increment recommended to maintain competitiveness."
        )
    elif gap_pct < -0.10:
        return (
            f"ABOVE_MARKET: Employee is {abs(gap_pct):.0%} above market median "
            f"({current_salary_egp:,.0f} vs {market_median_egp:,.0f} EGP). "
            "Strong increment may not be justified from a market perspective."
        )
    else:
        return (
            f"AT_MARKET: Employee salary is within ±10% of market median "
            f"({current_salary_egp:,.0f} EGP vs {market_median_egp:,.0f} EGP). "
            "Standard increment cycle applies."
        )


# ════════════════════════════════════════════════════════════════════════════
# 🏆  INCENTIVE TOOLS
# ════════════════════════════════════════════════════════════════════════════

@tool
def check_incentive_eligibility(
    kpi_achievement: float,
    incentive_type: str,
    is_on_pip: bool = False,
    tenure_months: int = 0,
    performance_score: float = 0.75,
) -> str:
    """
    Check if an employee is eligible for a specific incentive type.

    Args:
        kpi_achievement: KPI achievement ratio (0.0–1.0).
        incentive_type: Type of incentive (performance_bonus | spot_bonus | annual_profit_share
                        | overtime_compensation | retention_bonus).
        is_on_pip: Whether employee is on PIP.
        tenure_months: Months of employment.
        performance_score: Overall performance score (0.0–1.0).
    """
    incentive_lower = incentive_type.lower().strip()

    # Overtime compensation is always eligible regardless of performance
    if incentive_lower == "overtime_compensation":
        return (
            "ELIGIBLE: Overtime compensation is a statutory right under Egyptian Labor Law. "
            "Must be paid regardless of performance status."
        )

    # PIP block (except overtime)
    if is_on_pip:
        return (
            f"INELIGIBLE: Employee on PIP cannot receive {incentive_type}. "
            "PIP completion required before incentive eligibility is restored."
        )

    # Tenure check for profit share
    if incentive_lower == "annual_profit_share" and tenure_months < 12:
        return (
            f"INELIGIBLE: Annual profit share requires minimum 12 months tenure. "
            f"Employee has {tenure_months} months. Decision: DEFER to next cycle."
        )

    # KPI threshold for performance bonus
    if incentive_lower == "performance_bonus":
        if kpi_achievement < 0.70:
            return (
                f"INELIGIBLE: KPI achievement {kpi_achievement:.0%} is below the 70% minimum "
                "threshold for performance bonus. Decision: DENY."
            )
        elif kpi_achievement >= 1.20:
            return (
                f"FULLY_ELIGIBLE: Outstanding KPI achievement ({kpi_achievement:.0%}) — "
                "employee qualifies for maximum tier bonus."
            )
        elif kpi_achievement >= 1.0:
            return (
                f"ELIGIBLE: KPI target met at {kpi_achievement:.0%} — "
                "standard bonus tier applies."
            )
        else:
            return (
                f"PARTIALLY_ELIGIBLE: KPI achievement {kpi_achievement:.0%} qualifies for "
                f"partial bonus ({kpi_achievement:.0%} of target amount)."
            )

    # Spot bonus
    if incentive_lower == "spot_bonus":
        if performance_score >= 0.85:
            return (
                f"ELIGIBLE: High performer ({performance_score:.0%}) qualifies for spot recognition bonus."
            )
        elif performance_score >= 0.70:
            return (
                f"ELIGIBLE_WITH_REVIEW: Performance score {performance_score:.0%} is acceptable "
                "for spot bonus with manager justification."
            )
        else:
            return (
                f"QUESTIONABLE: Performance score {performance_score:.0%} makes spot bonus "
                "difficult to justify. Requires Director approval."
            )

    # Retention bonus
    if incentive_lower == "retention_bonus":
        if tenure_months >= 24 and performance_score >= 0.75:
            return (
                f"ELIGIBLE: Tenure {tenure_months}m + performance {performance_score:.0%} "
                "meets retention bonus criteria."
            )
        else:
            return (
                f"REVIEW_REQUIRED: Retention bonus for {tenure_months}m tenure / "
                f"{performance_score:.0%} performance requires HR Director justification."
            )

    return f"UNKNOWN_TYPE: Incentive type '{incentive_type}' not recognized. Manual review required."


@tool
def validate_bonus_budget(
    requested_amount_egp: float,
    monthly_salary_egp: float,
    incentive_budget_remaining_egp: float,
    incentive_type: str = "performance_bonus",
) -> str:
    """
    Validate that a bonus request fits within budget constraints.

    Args:
        requested_amount_egp: Requested bonus in EGP.
        monthly_salary_egp: Employee's monthly salary in EGP.
        incentive_budget_remaining_egp: Remaining incentive budget for the dept in EGP.
        incentive_type: Type of incentive.
    """
    if incentive_budget_remaining_egp <= 0:
        return (
            "BUDGET_EXHAUSTED: Department incentive budget is fully allocated. "
            "Decision: DEFER to next budget cycle."
        )

    if requested_amount_egp > incentive_budget_remaining_egp:
        shortfall = requested_amount_egp - incentive_budget_remaining_egp
        return (
            f"BUDGET_INSUFFICIENT: Requested {requested_amount_egp:,.0f} EGP exceeds "
            f"remaining budget of {incentive_budget_remaining_egp:,.0f} EGP "
            f"(shortfall: {shortfall:,.0f} EGP). "
            "Partial approval or deferral required."
        )

    # Salary multiple check
    if monthly_salary_egp > 0:
        multiple = requested_amount_egp / monthly_salary_egp
        if multiple > 3.0 and incentive_type != "annual_profit_share":
            return (
                f"ESCALATION_REQUIRED: Bonus amount ({requested_amount_egp:,.0f} EGP) is "
                f"{multiple:.1f}x monthly salary — exceeds 3x threshold. "
                "Requires CEO approval."
            )
        elif multiple > 1.5:
            return (
                f"DIRECTOR_APPROVAL: Bonus is {multiple:.1f}x monthly salary "
                f"({requested_amount_egp:,.0f} EGP). Requires HR Director sign-off. "
                f"Budget available: {incentive_budget_remaining_egp:,.0f} EGP."
            )

    utilization_after = (
        1.0 - (incentive_budget_remaining_egp - requested_amount_egp)
        / (incentive_budget_remaining_egp + requested_amount_egp)
    )
    return (
        f"BUDGET_OK: {requested_amount_egp:,.0f} EGP is within available budget "
        f"({incentive_budget_remaining_egp:,.0f} EGP remaining). "
        f"Approve."
    )


# ════════════════════════════════════════════════════════════════════════════
# 🚫  ABSENCE TOOLS
# ════════════════════════════════════════════════════════════════════════════

@tool
def analyze_absence_pattern(
    unexcused_count_90d: int,
    total_absences_90d: int,
    late_arrivals_90d: int,
    previous_warnings: str = "none",
) -> str:
    """
    Analyze absence patterns to detect concerning trends and recommend appropriate action.

    Args:
        unexcused_count_90d: Number of unexcused absences in last 90 days.
        total_absences_90d: Total absences in last 90 days.
        late_arrivals_90d: Number of late arrivals in last 90 days.
        previous_warnings: Previous warning level (none | written | formal).
    """
    findings: list[str] = []
    severity  = "none"

    # Egyptian Law: 3+ consecutive unexcused → termination right
    if unexcused_count_90d >= 3:
        findings.append(
            f"CRITICAL: {unexcused_count_90d} unexcused absences in 90 days triggers Egyptian "
            "Labor Law Art. 69 — employer has right to terminate. Immediate escalation required."
        )
        severity = "critical"
    elif unexcused_count_90d == 2:
        findings.append(
            f"HIGH RISK: {unexcused_count_90d} unexcused absences — one more triggers legal termination right. "
            "Formal warning mandatory."
        )
        severity = "major"
    elif unexcused_count_90d == 1:
        findings.append(f"WARNING: 1 unexcused absence — written warning and pay deduction apply.")
        severity = "minor"

    # Late arrival pattern
    if late_arrivals_90d >= 5:
        findings.append(
            f"PATTERN DETECTED: {late_arrivals_90d} late arrivals in 90 days — "
            "half-day deduction policy kicks in after 3/month."
        )
        severity = max(severity, "minor", key=lambda x: {"none": 0, "minor": 1, "major": 2, "critical": 3}.get(x, 0))

    # Escalating warnings
    if previous_warnings == "formal":
        findings.append(
            "ESCALATED: Employee already has a formal warning on record. "
            "Any new violation should trigger suspension/termination review."
        )
        severity = "critical" if severity in ("major", "critical") else "major"
    elif previous_warnings == "written":
        findings.append(
            "NOTE: Employee has a written warning on record. "
            "Next violation escalates to formal warning."
        )

    # Overall assessment
    if not findings:
        total_rate = total_absences_90d / 60  # approx working days
        if total_rate > 0.10:
            findings.append(
                f"MODERATE: Total absences ({total_absences_90d}/90d) represent "
                f"{total_rate:.0%} of working days — monitor trend."
            )
            severity = "minor"
        else:
            return "PATTERN_OK: No concerning absence pattern detected. Normal record."

    return f"SEVERITY={severity.upper()} | " + " | ".join(findings)


@tool
def compute_absence_deduction(
    daily_wage_egp: float,
    unexcused_days: float,
    is_second_offense: bool = False,
) -> str:
    """
    Compute the payroll deduction for unexcused absences per Egyptian Labor Law.

    Args:
        daily_wage_egp: Employee's daily wage in EGP.
        unexcused_days: Number of unexcused absence days to deduct.
        is_second_offense: Whether this is a second or subsequent offense.
    """
    if daily_wage_egp <= 0:
        return "CANNOT_COMPUTE: Daily wage not provided or is zero."

    multiplier   = 2.0 if is_second_offense else 1.0
    deduction    = daily_wage_egp * unexcused_days * multiplier
    offense_label = "2nd offense (double deduction)" if is_second_offense else "1st offense (single deduction)"

    return (
        f"DEDUCTION_COMPUTED: {unexcused_days:.1f} day(s) × {daily_wage_egp:,.0f} EGP/day "
        f"× {multiplier:.0f}x ({offense_label}) = {deduction:,.0f} EGP payroll deduction. "
        "Maximum per event: full day wage (Egyptian Law Art. 69)."
    )


# ════════════════════════════════════════════════════════════════════════════
# 📅  ATTENDANCE TOOLS
# ════════════════════════════════════════════════════════════════════════════

@tool
def evaluate_attendance_kpis(
    days_present: int,
    working_days: int,
    on_time_days: int,
    unexcused_absences: int,
    overtime_hours: float,
) -> str:
    """
    Calculate and evaluate monthly attendance KPIs against company thresholds.

    Args:
        days_present: Number of days the employee was present.
        working_days: Total working days in the month.
        on_time_days: Days the employee arrived on time.
        unexcused_absences: Number of unexcused absences.
        overtime_hours: Total overtime hours worked.
    """
    if working_days <= 0:
        return "INVALID_DATA: Working days must be greater than zero."

    att_rate   = days_present / working_days
    punct_rate = on_time_days / max(days_present, 1)
    results    = []
    overall    = "green"

    # Attendance rate
    if att_rate >= 0.95:
        results.append(f"✅ Attendance Rate: {att_rate:.1%} (GREEN — excellent)")
    elif att_rate >= 0.85:
        results.append(f"🟡 Attendance Rate: {att_rate:.1%} (YELLOW — acceptable)")
        overall = "yellow"
    else:
        results.append(f"🔴 Attendance Rate: {att_rate:.1%} (RED — below threshold 85%)")
        overall = "red"

    # Punctuality
    if punct_rate >= 0.90:
        results.append(f"✅ Punctuality: {punct_rate:.1%} (GREEN)")
    elif punct_rate >= 0.75:
        results.append(f"🟡 Punctuality: {punct_rate:.1%} (YELLOW)")
        overall = max(overall, "yellow", key=lambda x: {"green": 0, "yellow": 1, "red": 2}.get(x, 0))
    else:
        results.append(f"🔴 Punctuality: {punct_rate:.1%} (RED — below 75% threshold)")
        overall = "red"

    # Unexcused absences
    if unexcused_absences == 0:
        results.append("✅ Unexcused Absences: 0 (GREEN)")
    elif unexcused_absences <= 2:
        results.append(f"🟡 Unexcused Absences: {unexcused_absences} (YELLOW)")
        overall = max(overall, "yellow", key=lambda x: {"green": 0, "yellow": 1, "red": 2}.get(x, 0))
    else:
        results.append(f"🔴 Unexcused Absences: {unexcused_absences} (RED — 3+ triggers formal action)")
        overall = "red"

    # Overtime
    if overtime_hours > 60:
        results.append(
            f"⚠️ Overtime Hours: {overtime_hours:.0f}h (exceeds 60h monthly guideline — "
            "verify compliance with Egyptian Law Art. 56 — max 90h/year)"
        )

    return f"OVERALL_STATUS={overall.upper()} | " + " | ".join(results)


@tool
def recommend_attendance_action(
    overall_status: str,
    attendance_trend: str,
    ytd_warnings: int,
    attendance_rate: float,
) -> str:
    """
    Recommend the appropriate HR action based on attendance status and history.

    Args:
        overall_status: Current month status (green | yellow | red).
        attendance_trend: 3-month trend (improving | stable | declining).
        ytd_warnings: Number of warnings issued year-to-date.
        attendance_rate: Current attendance rate as decimal.
    """
    actions: list[str] = []

    status_lower = overall_status.lower()
    trend_lower  = attendance_trend.lower()

    if status_lower == "green":
        if ytd_warnings == 0:
            return (
                "NO_ACTION: Attendance is excellent. "
                "Consider adding a positive commendation in the employee's profile."
            )
        else:
            return (
                "POSITIVE_PROGRESS: Status improved to GREEN. "
                f"YTD warnings remain on record ({ytd_warnings}). Monitor next month."
            )

    if status_lower == "red":
        if attendance_rate < 0.70:
            actions.append("ESCALATE_TO_HR_DIRECTOR: Attendance below 70% — immediate intervention required.")
        elif ytd_warnings >= 2:
            actions.append(
                f"FORMAL_WARNING + ESCALATE: {ytd_warnings} YTD warnings already issued. "
                "Next violation → suspension review."
            )
        else:
            actions.append("FORMAL_WARNING: Issue formal warning letter. Document in personnel file.")

    elif status_lower == "yellow":
        if trend_lower == "declining":
            actions.append(
                "COUNSELING_SESSION: Schedule mandatory HR counseling. "
                "Declining trend on yellow status indicates early intervention needed."
            )
        else:
            actions.append(
                "MONITOR + ADVISORY: Send courtesy reminder about attendance expectations. "
                "Schedule check-in for next month."
            )

    if trend_lower == "declining" and status_lower != "green":
        actions.append(
            "TREND_ALERT: 3-month declining trend detected — "
            "consider root cause analysis (personal issues, workload, management)."
        )

    return " | ".join(actions) if actions else "NO_ACTION: Status acceptable."


# ════════════════════════════════════════════════════════════════════════════
# ⚖️  EGYPTIAN LABOR LAW CHECKER
# ════════════════════════════════════════════════════════════════════════════

@tool
def check_egyptian_labor_law(
    action_type: str,
    employee_tenure_months: int,
    situation_description: str,
) -> str:
    """
    Reference Egyptian Labor Law (No. 12/2003) for a specific HR action.
    Provides the relevant legal context and constraints.

    Args:
        action_type: Type of HR action (leave | dismissal | overtime | deduction | bonus).
        employee_tenure_months: Employee's tenure in months.
        situation_description: Brief description of the situation.
    """
    law_refs: dict[str, str] = {
        "leave": (
            "Egyptian Labor Law Art. 47: Minimum 21 days annual leave (30 days after 10 years). "
            "Art. 54: Sick leave up to 6 months with medical certificate. "
            "Art. 48: Emergency leave up to 7 days/year. "
            "Employer must grant leave within 60 days of request."
        ),
        "dismissal": (
            "Egyptian Labor Law Art. 69: Employer may terminate without notice for: "
            "(1) 3+ consecutive unexcused absences, (2) 20+ non-consecutive absences/year, "
            "(3) gross misconduct, (4) serious negligence causing significant loss. "
            "Art. 122: Termination without cause → 3 months notice or compensation. "
            f"Tenure {employee_tenure_months}m applies for end-of-service gratuity calculation."
        ),
        "overtime": (
            "Egyptian Labor Law Art. 56: Overtime limited to 2 hours/day. "
            "Art. 57: Overtime compensation = 1.35x hourly rate on normal days, "
            "2x on official holidays. "
            "Max 90 overtime hours/year without written employee consent."
        ),
        "deduction": (
            "Egyptian Labor Law Art. 69: Deductions for unexcused absence: "
            "1x daily wage for 1st offense, 2x for repeat offense. "
            "Total monthly deductions cannot exceed 5 days' wages. "
            "Art. 70: Employee must be notified in writing before any deduction."
        ),
        "bonus": (
            "Egyptian Labor Law Art. 41: Bonuses defined in employment contract are legally binding. "
            "Discretionary bonuses at employer discretion unless contractually promised. "
            "Profit-sharing schemes must be registered with Ministry of Manpower."
        ),
    }

    action_lower = action_type.lower().strip()
    law_text     = law_refs.get(action_lower, "No specific law reference found for this action type.")

    return (
        f"LEGAL_REFERENCE [{action_type.upper()}]: {law_text} "
        f"| Situation: {situation_description[:100]}..."
    )


# ════════════════════════════════════════════════════════════════════════════
# 💼  TOOL COLLECTIONS
# ════════════════════════════════════════════════════════════════════════════

#: All leave-related tools
LEAVE_TOOLS = [
    check_leave_policy,
    assess_team_risk,
    evaluate_performance_context,
]

#: All salary review tools
SALARY_TOOLS = [
    validate_salary_increment,
    check_market_benchmark,
    evaluate_performance_context,
    check_egyptian_labor_law,
]

#: All incentive/bonus tools
INCENTIVE_TOOLS = [
    check_incentive_eligibility,
    validate_bonus_budget,
    evaluate_performance_context,
    check_egyptian_labor_law,
]

#: All absence management tools
ABSENCE_TOOLS = [
    analyze_absence_pattern,
    compute_absence_deduction,
    check_egyptian_labor_law,
    evaluate_performance_context,
]

#: All attendance audit tools
ATTENDANCE_TOOLS = [
    evaluate_attendance_kpis,
    recommend_attendance_action,
    check_egyptian_labor_law,
]

#: Full toolkit (all tools combined)
ALL_HR_TOOLS = list({
    *LEAVE_TOOLS,
    *SALARY_TOOLS,
    *INCENTIVE_TOOLS,
    *ABSENCE_TOOLS,
    *ATTENDANCE_TOOLS,
})

#: Legacy alias for backward compatibility
HR_TOOLS = LEAVE_TOOLS