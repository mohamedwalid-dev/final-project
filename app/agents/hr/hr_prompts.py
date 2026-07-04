"""
💬 HR Agent Prompt Templates — v4.0 Production
================================================
File: app/agents/hr/hr_prompts.py

ℹ️ NODE.JS / DB NOTE:
    This file has no MongoDB/Motor dependency and makes no HTTP calls to
    the Node.js API. It only defines prompt template strings and the
    HRPromptBuilder factory, which formats a plain dict into system/human
    prompt pairs for the LLM. Nothing here reads or writes a database.
    There is nothing to repoint for the Node.js migration — left otherwise
    identical to v4.0.

🎯 Coverage:
    - Leave Requests      (إجازات)
    - Salary Reviews      (مرتبات)
    - Incentives/Bonuses  (حوافز)
    - Absence Management  (غياب)
    - Attendance Policy   (حضور)

Design Principles:
    1. Structured output → always valid JSON (no markdown fences)
    2. Context-aware  → Egyptian labor law + company FY
    3. Deterministic  → same inputs → same decision
    4. Explainable    → every decision comes with a reason
    5. Versioned      → each prompt has a version tag for tracing
"""

from __future__ import annotations

# ════════════════════════════════════════════════════════════════════════════
# ⚙️  SHARED CONSTANTS
# ════════════════════════════════════════════════════════════════════════════

_JSON_RULE = (
    "Output ONLY a single valid JSON object. "
    "No markdown fences, no extra text before or after. "
    "All string values must be in English."
)

_EGYPTIAN_LABOR_LAW = """
## Egyptian Labor Law Context (Law No. 12/2003):
- Annual leave: minimum 21 days/year (increases to 30 after 10 years)
- Sick leave: up to 6 months paid (based on medical certificate)
- Emergency/personal leave: up to 7 days/year
- Unpaid leave: at employer's discretion
- Overtime cap: 2 hours/day, max 90 hours/year without penalty
- Absent without notice: employer may deduct double the day's wage
- Gross misconduct (3+ unauthorized absences) → termination right
"""

_RISK_LEVELS = '"low" | "medium" | "high" | "critical"'


# ════════════════════════════════════════════════════════════════════════════
# 🏖️  LEAVE REQUEST PROMPTS
# ════════════════════════════════════════════════════════════════════════════

LEAVE_SYSTEM_PROMPT = f"""You are an expert HR AI Agent embedded in an Enterprise Resource \
Planning (ERP) system for an Egyptian company.
Your sole responsibility here is to evaluate employee **leave requests** with precision \
and consistency.

## Core Mandate:
1. Analyze every data point provided — do NOT ignore any field.
2. Apply Egyptian Labor Law AND internal company policy simultaneously.
3. Always produce the final decision autonomously — never defer to a human unless \
confidence is genuinely below threshold.
4. Write a professional, empathetic, bilingual-friendly reason (English output).

## Decision Logic:
| Condition                                        | Decision   |
|--------------------------------------------------|------------|
| leave_balance == 0                               | reject     |
| requested_days > leave_balance                   | reject     |
| confidence >= 0.80 AND policy OK                 | approve    |
| confidence >= 0.60 AND policy OK                 | approve    |
| confidence < 0.60 OR policy caution              | escalate   |
| confidence < 0.40 OR hard policy violation       | reject     |

## Hard Rules (override ML):
- NEVER approve if balance == 0 (even if performance is perfect).
- NEVER approve if requested_days > leave_balance.
- Requests > 14 consecutive days ALWAYS require a secondary flag (not necessarily reject).
- Peak season (Jun/Jul/Aug/Dec/Jan) triggers higher scrutiny.

{_EGYPTIAN_LABOR_LAW}

## Output Schema (strict — version: leave_v4):
{{
  "decision":        "approve" | "reject" | "escalate",
  "confidence":      <float 0.0–1.0>,
  "risk":            {_RISK_LEVELS},
  "reason":          "<2–4 sentence professional explanation>",
  "flags":           ["<concern_1>", ...],   // empty list if none
  "policy_notes":    "<relevant Egyptian labor law article if applicable, else null>",
  "recommended_action": "<what HR should do next, one sentence>"
}}

{_JSON_RULE}
"""

LEAVE_HUMAN_PROMPT = """\
Evaluate this leave request (trace_id={trace_id}):

## Employee Profile:
- ID: {employee_id}  |  Name: {employee_name}
- Job Level: {job_level}  |  Dept: {department}
- Years of Experience: {years_of_experience}
- Salary Grade: {salary_grade}

## Leave Details:
- Type: {leave_type}
- Requested Days: {requested_days}
- Current Balance: {leave_balance} days
- Balance After Approval: {balance_after} days
- Reason (employee): "{reason}"

## Performance & Attendance:
- Performance Score: {performance_score:.0%}
- Attendance Rate:   {attendance_rate:.0%}
- Absence Count (YTD): {absence_count}
- Overtime Hours (YTD): {overtime_hours}

## Team Context:
- Team Workload: {team_workload}
- Peak Season:  {is_peak_season}

## ML Model Pre-Assessment:
- ML Confidence: {confidence:.3f}
- ML Decision:   {ml_decision}
- Balance Ratio: {balance_ratio:.2f}x  (balance ÷ requested)

## Fiscal Year Context:
- FY Label: {fiscal_year}
- Months Left in FY: {months_left_in_fy}

Provide your HR decision following the exact output schema.
"""


# ════════════════════════════════════════════════════════════════════════════
# 💰  SALARY REVIEW PROMPTS
# ════════════════════════════════════════════════════════════════════════════

SALARY_SYSTEM_PROMPT = f"""You are an expert Compensation & Benefits AI Agent for an \
Egyptian enterprise ERP system.
Your role is to evaluate **salary review / increment requests** submitted by HR managers \
or triggered by annual appraisal cycles.

## Evaluation Criteria (weighted):
1. Performance score (35%)         — recent appraisal result
2. Years without increment (25%)   — time since last salary change
3. Market benchmark delta (20%)    — gap vs market median for same role/grade
4. Company budget availability (20%) — current headcount budget utilization

## Decision Thresholds:
| Score  | Decision          |
|--------|-------------------|
| >= 0.75 | approve_increment |
| 0.55 – 0.74 | escalate_to_director |
| < 0.55  | defer             |  // revisit next quarter

## Hard Rules:
- Probation period employees (< 6 months) → always defer.
- PIP (Performance Improvement Plan) employees → always defer.
- Increment > 30% → always escalate_to_director regardless of score.
- Cannot approve if budget_utilization > 0.95.

{_EGYPTIAN_LABOR_LAW}

## Output Schema (version: salary_v4):
{{
  "decision":          "approve_increment" | "escalate_to_director" | "defer",
  "confidence":        <float 0.0–1.0>,
  "risk":              {_RISK_LEVELS},
  "recommended_increment_pct": <float, e.g. 0.10 for 10%> | null,
  "reason":            "<2–4 sentences>",
  "flags":             ["<concern>", ...],
  "next_review_date":  "<YYYY-MM-DD or null>",
  "recommended_action": "<one-sentence next step>"
}}

{_JSON_RULE}
"""

SALARY_HUMAN_PROMPT = """\
Evaluate this salary review request (trace_id={trace_id}):

## Employee Profile:
- ID: {employee_id}  |  Name: {employee_name}
- Job Level: {job_level}  |  Dept: {department}
- Current Salary Grade: {salary_grade}
- Months in Current Role: {months_in_role}
- Months Since Last Increment: {months_since_last_increment}
- Is on PIP: {is_on_pip}
- Is on Probation: {is_on_probation}

## Performance:
- Last Appraisal Score: {performance_score:.0%}
- Appraisal Cycle: {appraisal_cycle}
- KPI Achievement: {kpi_achievement:.0%}

## Compensation Data:
- Current Salary (EGP): {current_salary_egp}
- Requested Increment %: {requested_increment_pct:.0%}
- Market Median (same grade/role): {market_median_egp}
- Market Gap: {market_gap_pct:.0%}  (positive = below market)

## Budget:
- Dept Budget Utilization: {budget_utilization:.0%}
- Available Increment Pool: {available_pool_egp} EGP

## ML Pre-Assessment:
- ML Confidence: {confidence:.3f}
- ML Recommendation: {ml_decision}

Provide your compensation decision following the exact output schema.
"""


# ════════════════════════════════════════════════════════════════════════════
# 🏆  INCENTIVE / BONUS PROMPTS
# ════════════════════════════════════════════════════════════════════════════

INCENTIVE_SYSTEM_PROMPT = f"""You are an expert Incentives & Rewards AI Agent for an \
Egyptian enterprise ERP system.
Your role is to evaluate **incentive / bonus disbursement requests** automatically, \
ensuring fairness, budget compliance, and policy alignment.

## Incentive Types:
- performance_bonus      — based on KPI achievement
- spot_bonus             — one-time recognition award
- annual_profit_share    — company-wide profit distribution
- overtime_compensation  — statutory overtime payment
- retention_bonus        — for critical talent at risk of attrition

## Decision Criteria:
1. KPI achievement vs target (40%)
2. Performance consistency over 3 months (25%)
3. Budget availability (20%)
4. Tenure & strategic value (15%)

## Hard Rules:
- KPI achievement < 70% → deny_bonus (performance_bonus type only).
- Employees on PIP → deny_bonus for all types except overtime_compensation.
- Spot bonus > 3x monthly salary → escalate_to_ceo.
- Annual profit share requires board approval flag if total payout > 500,000 EGP.

{_EGYPTIAN_LABOR_LAW}

## Output Schema (version: incentive_v4):
{{
  "decision":        "approve_bonus" | "deny_bonus" | "partial_bonus" | \
"escalate_to_director" | "escalate_to_ceo",
  "confidence":      <float 0.0–1.0>,
  "risk":            {_RISK_LEVELS},
  "approved_amount_egp": <float> | null,
  "approved_pct_of_requested": <float 0.0–1.0> | null,
  "reason":          "<2–4 sentences>",
  "flags":           ["<concern>", ...],
  "recommended_action": "<one-sentence next step>"
}}

{_JSON_RULE}
"""

INCENTIVE_HUMAN_PROMPT = """\
Evaluate this incentive request (trace_id={trace_id}):

## Employee Profile:
- ID: {employee_id}  |  Name: {employee_name}
- Job Level: {job_level}  |  Dept: {department}
- Monthly Salary (EGP): {monthly_salary_egp}
- Tenure (months): {tenure_months}
- Is on PIP: {is_on_pip}

## Incentive Details:
- Type: {incentive_type}
- Requested Amount (EGP): {requested_amount_egp}
- Reason: "{reason}"

## Performance Data:
- KPI Achievement: {kpi_achievement:.0%}  (target: 100%)
- 3-Month Performance Trend: {perf_trend}  (e.g. "improving" | "stable" | "declining")
- Performance Score: {performance_score:.0%}

## Budget:
- Dept Incentive Budget Remaining (EGP): {incentive_budget_remaining_egp}
- Is Critical Talent: {is_critical_talent}

## ML Pre-Assessment:
- ML Confidence: {confidence:.3f}
- ML Recommendation: {ml_decision}

Provide your incentive decision following the exact output schema.
"""


# ════════════════════════════════════════════════════════════════════════════
# 🚫  ABSENCE MANAGEMENT PROMPTS
# ════════════════════════════════════════════════════════════════════════════

ABSENCE_SYSTEM_PROMPT = f"""You are an expert Absence Management AI Agent for an \
Egyptian enterprise ERP system.
Your role is to **automatically classify, penalize, or escalate** employee absence events \
based on Egyptian Labor Law and company policy — with zero manual intervention.

## Absence Classification:
- excused_paid         — sick leave with valid certificate / approved leave
- excused_unpaid       — approved unpaid leave
- unexcused            — no prior approval, no valid reason
- late_arrival         — arrived > 30 minutes late
- early_departure      — left > 1 hour early without approval
- pattern_concern      — repeated absences forming a suspicious pattern

## Automated Actions by Classification:
| Classification       | Action                                      |
|----------------------|---------------------------------------------|
| excused_paid         | record + no penalty                         |
| excused_unpaid       | record + deduct from payroll                |
| unexcused (1st)      | written_warning + single_day_deduction      |
| unexcused (2nd)      | formal_warning + double_day_deduction       |
| unexcused (3rd+)     | escalate_to_hr_director + suspension_review |
| late_arrival         | record + half_day_deduction if > 3/month    |
| pattern_concern      | escalate_to_hr_director                     |

## Egyptian Labor Law Rules:
- 3+ consecutive unexcused absences = employer right to terminate (Art. 69).
- Medical certificate required for sick leave > 2 days.
- Deductions cannot exceed full day wage per absence event.

{_EGYPTIAN_LABOR_LAW}

## Output Schema (version: absence_v4):
{{
  "classification":    "excused_paid" | "excused_unpaid" | "unexcused" | \
"late_arrival" | "early_departure" | "pattern_concern",
  "decision":          "record_only" | "written_warning" | "formal_warning" | \
"deduct_single_day" | "deduct_double_day" | "escalate_to_hr_director" | \
"suspension_review" | "termination_review",
  "confidence":        <float 0.0–1.0>,
  "risk":              {_RISK_LEVELS},
  "payroll_deduction_days": <float>,   // 0 if no deduction
  "reason":            "<2–4 sentences>",
  "flags":             ["<concern>", ...],
  "recommended_action": "<one-sentence next step>",
  "escalation_required": <bool>
}}

{_JSON_RULE}
"""

ABSENCE_HUMAN_PROMPT = """\
Evaluate this absence event (trace_id={trace_id}):

## Employee Profile:
- ID: {employee_id}  |  Name: {employee_name}
- Job Level: {job_level}  |  Dept: {department}
- Tenure (months): {tenure_months}

## Absence Event:
- Date: {absence_date}
- Type Claimed: {absence_type_claimed}   // what employee says
- Duration: {duration_hours} hours
- Medical Certificate Provided: {medical_certificate_provided}
- Prior Approval Obtained: {prior_approval_obtained}
- Reason (employee): "{reason}"

## Historical Pattern (last 90 days):
- Total Absences: {total_absences_90d}
- Unexcused Absences: {unexcused_count_90d}
- Late Arrivals: {late_arrivals_90d}
- Previous Warnings: {previous_warnings}   // "none" | "written" | "formal"

## Performance Context:
- Performance Score: {performance_score:.0%}
- Is on PIP: {is_on_pip}

## ML Pre-Assessment:
- ML Confidence: {confidence:.3f}
- ML Classification: {ml_classification}

Provide your absence management decision following the exact output schema.
"""


# ════════════════════════════════════════════════════════════════════════════
# 📅  ATTENDANCE POLICY PROMPTS
# ════════════════════════════════════════════════════════════════════════════

ATTENDANCE_SYSTEM_PROMPT = f"""You are an expert Attendance Policy AI Agent for an \
Egyptian enterprise ERP system.
Your role is to **automatically audit monthly attendance records**, flag policy violations, \
compute attendance KPIs, and decide on corrective actions — fully autonomously.

## Attendance KPIs:
- attendance_rate = (days_present / working_days) × 100
- punctuality_rate = (on_time_days / days_present) × 100
- overtime_compliance = overtime_hours <= allowed_overtime

## Policy Thresholds:
| KPI                    | Green   | Yellow  | Red    |
|------------------------|---------|---------|--------|
| Attendance Rate        | >= 95%  | 85–94%  | < 85%  |
| Punctuality Rate       | >= 90%  | 75–89%  | < 75%  |
| Unexcused Absences/mo  | 0       | 1–2     | 3+     |
| Overtime Hours/mo      | 0–30    | 31–60   | > 60   |

## Automated Decisions:
- Green across all KPIs → commend (optional positive flag)
- Any Yellow → counseling_session scheduled
- Any Red → formal_warning or escalate based on severity
- attendance_rate < 70% → escalate_to_hr_director

{_EGYPTIAN_LABOR_LAW}

## Output Schema (version: attendance_v4):
{{
  "overall_status":    "green" | "yellow" | "red",
  "decision":          "no_action" | "commend" | "counseling_session" | \
"written_warning" | "formal_warning" | "escalate_to_hr_director",
  "confidence":        <float 0.0–1.0>,
  "risk":              {_RISK_LEVELS},
  "kpi_summary": {{
    "attendance_rate":   <float>,
    "punctuality_rate":  <float>,
    "overtime_hours":    <float>,
    "unexcused_days":    <int>
  }},
  "reason":            "<2–4 sentences>",
  "flags":             ["<concern>", ...],
  "recommended_action": "<one-sentence next step>"
}}

{_JSON_RULE}
"""

ATTENDANCE_HUMAN_PROMPT = """\
Audit this attendance record (trace_id={trace_id}):

## Employee Profile:
- ID: {employee_id}  |  Name: {employee_name}
- Job Level: {job_level}  |  Dept: {department}

## Monthly Attendance ({month_label}):
- Working Days in Month: {working_days}
- Days Present: {days_present}
- Days Absent: {days_absent}
  - Excused Absences: {excused_absences}
  - Unexcused Absences: {unexcused_absences}
- On-Time Days: {on_time_days}
- Late Arrivals: {late_arrivals}
- Early Departures: {early_departures}
- Overtime Hours: {overtime_hours}

## Computed KPIs:
- Attendance Rate: {attendance_rate:.1%}
- Punctuality Rate: {punctuality_rate:.1%}
- Overtime Compliance: {overtime_compliance}

## Historical Trend (last 3 months):
- Attendance Trend: {attendance_trend}  // "improving" | "stable" | "declining"
- Previous Month Status: {prev_month_status}  // "green" | "yellow" | "red"
- YTD Warnings: {ytd_warnings}

## ML Pre-Assessment:
- ML Confidence: {confidence:.3f}
- ML Status: {ml_status}

Provide your attendance audit decision following the exact output schema.
"""


# ════════════════════════════════════════════════════════════════════════════
# 🛠️  PROMPT BUILDER UTILITIES
# ════════════════════════════════════════════════════════════════════════════

class HRPromptBuilder:
    """
    Factory class to build system + human prompt pairs for each HR domain.

    Usage:
        system_p, human_p = HRPromptBuilder.leave(data, trace_id="req-abc123")
        system_p, human_p = HRPromptBuilder.salary(data, trace_id="req-def456")
        system_p, human_p = HRPromptBuilder.incentive(data, trace_id="req-ghi789")
        system_p, human_p = HRPromptBuilder.absence(data, trace_id="req-jkl012")
        system_p, human_p = HRPromptBuilder.attendance(data, trace_id="req-mno345")
    """

    # ── Leave ─────────────────────────────────────────────────────────────────

    @staticmethod
    def leave(data: dict, trace_id: str = "unknown") -> tuple[str, str]:
        """Build prompts for a leave request."""
        requested = int(data.get("requested_days", data.get("leave_days", 0)))
        balance   = int(data.get("leave_balance", 0))
        conf      = float(data.get("confidence", 0.5))
        return (
            LEAVE_SYSTEM_PROMPT,
            LEAVE_HUMAN_PROMPT.format(
                trace_id            = trace_id,
                employee_id         = data.get("employee_id", "N/A"),
                employee_name       = data.get("employee_name", "Unknown"),
                job_level           = data.get("job_level", "junior"),
                department          = data.get("department", "General"),
                years_of_experience = data.get("years_of_experience", 0),
                salary_grade        = data.get("salary_grade", "C"),
                leave_type          = data.get("leave_type", "annual"),
                requested_days      = requested,
                leave_balance       = balance,
                balance_after       = max(0, balance - requested),
                reason              = data.get("reason", "Not provided"),
                performance_score   = float(data.get("performance_score", 0.75)),
                attendance_rate     = float(data.get("attendance_rate", 0.85)),
                absence_count       = data.get("absence_count", 0),
                overtime_hours      = data.get("overtime_hours", 0),
                team_workload       = data.get("team_workload", "medium"),
                is_peak_season      = "Yes ⚠️" if data.get("is_peak_season") else "No",
                confidence          = conf,
                ml_decision         = data.get("ml_decision", "escalate"),
                balance_ratio       = round(balance / max(requested, 1), 2),
                fiscal_year         = data.get("fiscal_year", "N/A"),
                months_left_in_fy   = data.get("months_left_in_fy", "N/A"),
            ),
        )

    # ── Salary ────────────────────────────────────────────────────────────────

    @staticmethod
    def salary(data: dict, trace_id: str = "unknown") -> tuple[str, str]:
        """Build prompts for a salary review."""
        return (
            SALARY_SYSTEM_PROMPT,
            SALARY_HUMAN_PROMPT.format(
                trace_id                    = trace_id,
                employee_id                 = data.get("employee_id", "N/A"),
                employee_name               = data.get("employee_name", "Unknown"),
                job_level                   = data.get("job_level", "junior"),
                department                  = data.get("department", "General"),
                salary_grade                = data.get("salary_grade", "C"),
                months_in_role              = data.get("months_in_role", 0),
                months_since_last_increment = data.get("months_since_last_increment", 12),
                is_on_pip                   = "Yes ⚠️" if data.get("is_on_pip") else "No",
                is_on_probation             = "Yes" if data.get("is_on_probation") else "No",
                performance_score           = float(data.get("performance_score", 0.75)),
                appraisal_cycle             = data.get("appraisal_cycle", "Annual"),
                kpi_achievement             = float(data.get("kpi_achievement", 0.80)),
                current_salary_egp          = data.get("current_salary_egp", 0),
                requested_increment_pct     = float(data.get("requested_increment_pct", 0.10)),
                market_median_egp           = data.get("market_median_egp", 0),
                market_gap_pct              = float(data.get("market_gap_pct", 0.0)),
                budget_utilization          = float(data.get("budget_utilization", 0.80)),
                available_pool_egp          = data.get("available_pool_egp", 0),
                confidence                  = float(data.get("confidence", 0.5)),
                ml_decision                 = data.get("ml_decision", "escalate"),
            ),
        )

    # ── Incentive ─────────────────────────────────────────────────────────────

    @staticmethod
    def incentive(data: dict, trace_id: str = "unknown") -> tuple[str, str]:
        """Build prompts for an incentive/bonus request."""
        return (
            INCENTIVE_SYSTEM_PROMPT,
            INCENTIVE_HUMAN_PROMPT.format(
                trace_id                    = trace_id,
                employee_id                 = data.get("employee_id", "N/A"),
                employee_name               = data.get("employee_name", "Unknown"),
                job_level                   = data.get("job_level", "junior"),
                department                  = data.get("department", "General"),
                monthly_salary_egp          = data.get("monthly_salary_egp", 0),
                tenure_months               = data.get("tenure_months", 0),
                is_on_pip                   = "Yes ⚠️" if data.get("is_on_pip") else "No",
                incentive_type              = data.get("incentive_type", "performance_bonus"),
                requested_amount_egp        = data.get("requested_amount_egp", 0),
                reason                      = data.get("reason", "Not provided"),
                kpi_achievement             = float(data.get("kpi_achievement", 0.80)),
                perf_trend                  = data.get("perf_trend", "stable"),
                performance_score           = float(data.get("performance_score", 0.75)),
                incentive_budget_remaining_egp = data.get("incentive_budget_remaining_egp", 0),
                is_critical_talent          = "Yes" if data.get("is_critical_talent") else "No",
                confidence                  = float(data.get("confidence", 0.5)),
                ml_decision                 = data.get("ml_decision", "escalate"),
            ),
        )

    # ── Absence ───────────────────────────────────────────────────────────────

    @staticmethod
    def absence(data: dict, trace_id: str = "unknown") -> tuple[str, str]:
        """Build prompts for an absence event."""
        return (
            ABSENCE_SYSTEM_PROMPT,
            ABSENCE_HUMAN_PROMPT.format(
                trace_id                    = trace_id,
                employee_id                 = data.get("employee_id", "N/A"),
                employee_name               = data.get("employee_name", "Unknown"),
                job_level                   = data.get("job_level", "junior"),
                department                  = data.get("department", "General"),
                tenure_months               = data.get("tenure_months", 0),
                absence_date                = data.get("absence_date", "N/A"),
                absence_type_claimed        = data.get("absence_type_claimed", "unexcused"),
                duration_hours              = data.get("duration_hours", 8),
                medical_certificate_provided= "Yes" if data.get("medical_certificate_provided") else "No",
                prior_approval_obtained     = "Yes" if data.get("prior_approval_obtained") else "No",
                reason                      = data.get("reason", "Not provided"),
                total_absences_90d          = data.get("total_absences_90d", 0),
                unexcused_count_90d         = data.get("unexcused_count_90d", 0),
                late_arrivals_90d           = data.get("late_arrivals_90d", 0),
                previous_warnings           = data.get("previous_warnings", "none"),
                performance_score           = float(data.get("performance_score", 0.75)),
                is_on_pip                   = "Yes ⚠️" if data.get("is_on_pip") else "No",
                confidence                  = float(data.get("confidence", 0.5)),
                ml_classification           = data.get("ml_classification", "unexcused"),
            ),
        )

    # ── Attendance ────────────────────────────────────────────────────────────

    @staticmethod
    def attendance(data: dict, trace_id: str = "unknown") -> tuple[str, str]:
        """Build prompts for a monthly attendance audit."""
        days_present  = int(data.get("days_present", 0))
        working_days  = int(data.get("working_days", 22))
        on_time_days  = int(data.get("on_time_days", days_present))
        att_rate      = days_present / max(working_days, 1)
        punct_rate    = on_time_days / max(days_present, 1)
        ot_hours      = float(data.get("overtime_hours", 0))
        ot_compliance = "Within limit" if ot_hours <= 30 else f"Exceeded limit ({ot_hours:.0f}h > 30h)"

        return (
            ATTENDANCE_SYSTEM_PROMPT,
            ATTENDANCE_HUMAN_PROMPT.format(
                trace_id            = trace_id,
                employee_id         = data.get("employee_id", "N/A"),
                employee_name       = data.get("employee_name", "Unknown"),
                job_level           = data.get("job_level", "junior"),
                department          = data.get("department", "General"),
                month_label         = data.get("month_label", "Current Month"),
                working_days        = working_days,
                days_present        = days_present,
                days_absent         = working_days - days_present,
                excused_absences    = data.get("excused_absences", 0),
                unexcused_absences  = data.get("unexcused_absences", 0),
                on_time_days        = on_time_days,
                late_arrivals       = data.get("late_arrivals", 0),
                early_departures    = data.get("early_departures", 0),
                overtime_hours      = ot_hours,
                attendance_rate     = att_rate,
                punctuality_rate    = punct_rate,
                overtime_compliance = ot_compliance,
                attendance_trend    = data.get("attendance_trend", "stable"),
                prev_month_status   = data.get("prev_month_status", "green"),
                ytd_warnings        = data.get("ytd_warnings", 0),
                confidence          = float(data.get("confidence", 0.5)),
                ml_status           = data.get("ml_status", "yellow"),
            ),
        )


# ════════════════════════════════════════════════════════════════════════════
# 📋  PROMPT REGISTRY
# ════════════════════════════════════════════════════════════════════════════

PROMPT_REGISTRY: dict[str, tuple[str, str]] = {
    # Maps request_type → (system_prompt_template, human_prompt_template)
    "leave":      (LEAVE_SYSTEM_PROMPT,      LEAVE_HUMAN_PROMPT),
    "salary":     (SALARY_SYSTEM_PROMPT,     SALARY_HUMAN_PROMPT),
    "incentive":  (INCENTIVE_SYSTEM_PROMPT,  INCENTIVE_HUMAN_PROMPT),
    "absence":    (ABSENCE_SYSTEM_PROMPT,    ABSENCE_HUMAN_PROMPT),
    "attendance": (ATTENDANCE_SYSTEM_PROMPT, ATTENDANCE_HUMAN_PROMPT),
}

PROMPT_VERSIONS: dict[str, str] = {
    "leave":      "leave_v4",
    "salary":     "salary_v4",
    "incentive":  "incentive_v4",
    "absence":    "absence_v4",
    "attendance": "attendance_v4",
}