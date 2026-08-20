import frappe
from frappe.utils import nowdate, add_days, get_first_day, getdate, flt, cint, date_diff
from datetime import date, timedelta
from collections import defaultdict


#  Date range helpers
def _get_date_range(period):
    today = getdate(nowdate())

    if period == "today":
        from_date = to_date = today
    elif period == "yesterday":
        from_date = to_date = today - timedelta(days=1)
    elif period == "this_week":
        from_date = today - timedelta(days=today.weekday())
        to_date = today
    elif period == "last_7_days":
        from_date = today - timedelta(days=6)
        to_date = today
    elif period == "this_month":
        from_date = get_first_day(today)
        to_date = today
    elif period == "last_month":
        first_this = get_first_day(today)
        to_date = first_this - timedelta(days=1)
        from_date = get_first_day(to_date)
    elif period == "last_30_days":
        from_date = today - timedelta(days=29)
        to_date = today
    elif period == "this_quarter":
        q = (today.month - 1) // 3
        from_date = date(today.year, q * 3 + 1, 1)
        to_date = today
    elif period == "this_year":
        from_date = date(today.year, 1, 1)
        to_date = today
    else:
        from_date = today - timedelta(days=29)
        to_date = today

    span = date_diff(to_date, from_date)
    prev_to = from_date - timedelta(days=1)
    prev_from = prev_to - timedelta(days=span)

    return str(from_date), str(to_date), str(prev_from), str(prev_to)


def _pct_change(current, previous):
    if not previous:
        return 100.0 if current else 0.0
    return round(((current - previous) / previous) * 100, 1)


#  Product resolution
def _get_plan_project_map():
    rows = frappe.db.sql(
        "SELECT plan_name, custom_project FROM `tabSubscription Plan` WHERE custom_project IS NOT NULL AND custom_project != ''",
        as_dict=True,
    )
    return {r.plan_name: r.custom_project for r in rows}


def _subscription_project_map():
    rows = frappe.db.sql(
        """
        SELECT spd.parent AS subscription, sp.custom_project AS project
        FROM `tabSubscription Plan Detail` spd
        INNER JOIN `tabSubscription Plan` sp ON (sp.name = spd.plan OR sp.plan_name = spd.plan)
        WHERE sp.custom_project IS NOT NULL AND sp.custom_project != ''
    """,
        as_dict=True,
    )

    mapping = {}
    for r in rows:
        if r.subscription not in mapping:
            mapping[r.subscription] = r.project
    return mapping


#  Subscription filters
def _get_subscriptions_in_period(from_date, to_date, project=None, status=None):
    conds = [
        "(s.start_date BETWEEN %(from_date)s AND %(to_date)s OR DATE(s.creation) BETWEEN %(from_date)s AND %(to_date)s)",
        "s.docstatus != 2",
    ]
    params = {"from_date": from_date, "to_date": to_date}

    if status and status != "all":
        conds.append("s.status = %(status)s")
        params["status"] = status

    if project and project != "all":
        conds.append(
            """
            EXISTS (
                SELECT 1 FROM `tabSubscription Plan Detail` spd
                INNER JOIN `tabSubscription Plan` sp ON (sp.name = spd.plan OR sp.plan_name = spd.plan)
                WHERE spd.parent = s.name AND sp.custom_project = %(project)s
            )
        """
        )
        params["project"] = project

    where = " AND ".join(conds)
    rows = frappe.db.sql(
        f"SELECT s.name FROM `tabSubscription` s WHERE {where}", params, as_dict=True
    )
    return [r.name for r in rows]


def _count_subscriptions(from_date, to_date, project=None, status=None):
    return len(_get_subscriptions_in_period(from_date, to_date, project, status))


#  Revenue split
def _get_revenue_split(from_date, to_date, project=None, team=None):
    conds = [
        "si.docstatus = 1",
        "si.status IN ('Paid', 'Return')",
        "si.posting_date BETWEEN %(from_date)s AND %(to_date)s",
    ]
    params = {"from_date": from_date, "to_date": to_date}

    if project and project != "all":
        conds.append(
            """
            (
                EXISTS (
                    SELECT 1 FROM `tabSubscription Plan` sp
                    WHERE (sp.name = si.custom_plan OR sp.plan_name = si.custom_plan)
                      AND sp.custom_project = %(project)s
                )
                OR EXISTS (
                    SELECT 1 FROM `tabSubscription Plan Detail` spd
                    INNER JOIN `tabSubscription Plan` sp ON (sp.name = spd.plan OR sp.plan_name = spd.plan)
                    WHERE spd.parent = si.subscription AND sp.custom_project = %(project)s
                )
            )
        """
        )
        params["project"] = project

    if team and team != "all":
        conds.append(
            """
            (
                si.owner = %(team)s
                OR EXISTS (
                    SELECT 1 FROM `tabCustomer` c
                    WHERE c.name = si.customer AND c.owner = %(team)s
                )
                OR EXISTS (
                    SELECT 1 FROM `tabCRM Deal` d
                    LEFT JOIN `tabCRM Lead` l ON l.name = d.lead
                    LEFT JOIN `tabCustomer` c ON c.name = si.customer
                    WHERE (d.erpnext_customer = si.customer OR c.crm_deal = d.name)
                      AND (
                        d.deal_owner = %(team)s
                        OR d.owner = %(team)s
                        OR l.lead_owner = %(team)s
                        OR l.owner = %(team)s
                      )
                )
            )
        """
        )
        params["team"] = team

    where = " AND ".join(conds)
    invoices = frappe.db.sql(
        f"""
        SELECT si.name, si.grand_total, si.customer, si.subscription, si.posting_date
        FROM `tabSales Invoice` si
        WHERE {where}
        ORDER BY si.posting_date ASC, si.creation ASC
    """,
        params,
        as_dict=True,
    )

    new_revenue = 0.0
    renewal_revenue = 0.0
    new_customers = set()
    renewals = 0

    for inv in invoices:
        is_renewal = False
        if inv.customer:
            earlier = frappe.db.count(
                "Sales Invoice",
                {
                    "customer": inv.customer,
                    "docstatus": 1,
                    "status": ["in", ["Paid", "Return"]],
                    "posting_date": ["<", from_date],
                },
            )
            if earlier > 0:
                is_renewal = True
            else:
                first_inv = frappe.db.sql(
                    """
                    SELECT name FROM `tabSales Invoice`
                    WHERE customer = %(customer)s AND docstatus = 1 AND status IN ('Paid', 'Return')
                    ORDER BY posting_date ASC, creation ASC
                    LIMIT 1
                """,
                    {"customer": inv.customer},
                    as_dict=True,
                )
                if first_inv and first_inv[0].name != inv.name:
                    is_renewal = True

        if is_renewal:
            renewal_revenue += flt(inv.grand_total)
            renewals += 1
        else:
            new_revenue += flt(inv.grand_total)
            new_customers.add(inv.customer)

    expired_in_period = _count_expired_in_period(from_date, to_date, project)
    total_due = renewals + expired_in_period
    renewal_rate = round((renewals / total_due * 100), 1) if total_due else 0.0

    return {
        "new_revenue": round(new_revenue, 2),
        "renewal_revenue": round(renewal_revenue, 2),
        "new_customers": len(new_customers),
        "renewals": renewals,
        "renewal_rate": renewal_rate,
    }


def _count_expired_in_period(from_date, to_date, project=None):
    conds = [
        "s.end_date BETWEEN %(from_date)s AND %(to_date)s",
        "s.status = 'Expired'",
        "s.docstatus != 2",
    ]
    params = {"from_date": from_date, "to_date": to_date}
    if project and project != "all":
        conds.append(
            """
            EXISTS (
                SELECT 1 FROM `tabSubscription Plan Detail` spd
                INNER JOIN `tabSubscription Plan` sp ON (sp.name = spd.plan OR sp.plan_name = spd.plan)
                WHERE spd.parent = s.name AND sp.custom_project = %(project)s
            )
        """
        )
        params["project"] = project
    where = " AND ".join(conds)
    rows = frappe.db.sql(
        f"SELECT COUNT(*) as cnt FROM `tabSubscription` s WHERE {where}",
        params,
        as_dict=True,
    )
    return cint(rows[0].cnt) if rows else 0


def _get_churn_stats(project=None):
    today = getdate(nowdate())

    def count_expired_within(days):
        cutoff = str(today - timedelta(days=days))
        conds = [
            "s.status = 'Expired'",
            "s.docstatus != 2",
            "s.end_date >= %(cutoff)s",
            "s.end_date <= %(today)s",
        ]
        params = {"cutoff": str(cutoff), "today": str(today)}
        if project and project != "all":
            conds.append(
                """
                EXISTS (
                    SELECT 1 FROM `tabSubscription Plan Detail` spd
                    INNER JOIN `tabSubscription Plan` sp ON (sp.name = spd.plan OR sp.plan_name = spd.plan)
                    WHERE spd.parent = s.name AND sp.custom_project = %(project)s
                )
            """
            )
            params["project"] = project
        where = " AND ".join(conds)
        rows = frappe.db.sql(
            f"SELECT COUNT(*) as cnt FROM `tabSubscription` s WHERE {where}",
            params,
            as_dict=True,
        )
        return cint(rows[0].cnt) if rows else 0

    def count_total_expired():
        conds = ["s.status = 'Expired'", "s.docstatus != 2"]
        params = {}
        if project and project != "all":
            conds.append(
                """
                EXISTS (
                    SELECT 1 FROM `tabSubscription Plan Detail` spd
                    INNER JOIN `tabSubscription Plan` sp ON (sp.name = spd.plan OR sp.plan_name = spd.plan)
                    WHERE spd.parent = s.name AND sp.custom_project = %(project)s
                )
            """
            )
            params["project"] = project
        where = " AND ".join(conds)
        rows = frappe.db.sql(
            f"SELECT COUNT(*) as cnt FROM `tabSubscription` s WHERE {where}",
            params,
            as_dict=True,
        )
        return cint(rows[0].cnt) if rows else 0

    # Lost MRR from custom_cost field
    mrr_conds = ["s.status = 'Expired'", "s.docstatus != 2"]
    mrr_params = {}
    if project and project != "all":
        mrr_conds.append(
            """
            EXISTS (
                SELECT 1 FROM `tabSubscription Plan Detail` spd
                INNER JOIN `tabSubscription Plan` sp ON (sp.name = spd.plan OR sp.plan_name = spd.plan)
                WHERE spd.parent = s.name AND sp.custom_project = %(project)s
            )
        """
        )
        mrr_params["project"] = project
    mrr_where = " AND ".join(mrr_conds)
    lost_mrr_rows = frappe.db.sql(
        f"SELECT COALESCE(SUM(s.custom_cost), 0) as val FROM `tabSubscription` s WHERE {mrr_where}",
        mrr_params,
        as_dict=True,
    )
    lost_mrr = flt(lost_mrr_rows[0].val) if lost_mrr_rows else 0.0

    expired_lt_3 = count_expired_within(3)
    expired_lt_7 = count_expired_within(7)

    return {
        "total": count_total_expired(),
        "expired_lt_3": expired_lt_3,
        "expired_lt_7": expired_lt_7,
        "expired_gt_3": expired_lt_3,
        "expired_gt_7": expired_lt_7,
        "lost_mrr": round(lost_mrr, 2),
        "change_pct": 0,
    }


#  Whitelisted API Endpoints
@frappe.whitelist()
def get_top_kpis(period="last_30_days", product=None, team=None, status=None):
    from_date, to_date, prev_from, prev_to = _get_date_range(period)

    # Subscriptions
    new_subs_cur = _count_subscriptions(from_date, to_date, product, status)
    new_subs_prev = _count_subscriptions(prev_from, prev_to, product, status)
    today_str = nowdate()
    today_dt = getdate(today_str)
    week_start = str(today_dt - timedelta(days=today_dt.weekday()))
    new_subs_today = _count_subscriptions(today_str, today_str, product, status)
    new_subs_week = _count_subscriptions(week_start, today_str, product, status)

    # Revenue
    rev = _get_revenue_split(from_date, to_date, product, team)
    prev_rev = _get_revenue_split(prev_from, prev_to, product, team)
    total = rev["new_revenue"] + rev["renewal_revenue"]
    prev_tot = prev_rev["new_revenue"] + prev_rev["renewal_revenue"]

    # Churn
    churn = _get_churn_stats(product)

    return {
        "currency": frappe.db.get_default("currency") or "USD",
        "subscriptions": {
            "current": new_subs_cur,
            "prev": new_subs_prev,
            "change_pct": _pct_change(new_subs_cur, new_subs_prev),
            "today": new_subs_today,
            "this_week": new_subs_week,
        },
        "first_payment": {
            "revenue": rev["new_revenue"],
            "prev_revenue": prev_rev["new_revenue"],
            "change_pct": _pct_change(rev["new_revenue"], prev_rev["new_revenue"]),
            "paying_customers": rev["new_customers"],
            "avg_first_payment": (
                round(rev["new_revenue"] / rev["new_customers"], 2)
                if rev["new_customers"]
                else 0
            ),
            "conversion_pct": (
                round(rev["new_customers"] / new_subs_cur * 100, 1)
                if new_subs_cur
                else 0
            ),
        },
        "renewal": {
            "revenue": rev["renewal_revenue"],
            "prev_revenue": prev_rev["renewal_revenue"],
            "change_pct": _pct_change(
                rev["renewal_revenue"], prev_rev["renewal_revenue"]
            ),
            "renewals": rev["renewals"],
            "renewal_rate_pct": rev["renewal_rate"],
            "avg_renewal_value": (
                round(rev["renewal_revenue"] / rev["renewals"], 2)
                if rev["renewals"]
                else 0
            ),
        },
        "total_collection": {
            "revenue": total,
            "prev_revenue": prev_tot,
            "change_pct": _pct_change(total, prev_tot),
            "new_revenue": rev["new_revenue"],
            "renewal_revenue": rev["renewal_revenue"],
        },
        "churn": churn,
    }


@frappe.whitelist()
def get_revenue_trend(period="last_30_days", product=None, team=None, groupby="daily"):
    from_date, to_date, _, _ = _get_date_range(period)

    if groupby == "monthly":
        date_expr = "DATE_FORMAT(si.posting_date, '%%Y-%%m')"
    elif groupby == "weekly":
        date_expr = "DATE_FORMAT(si.posting_date, '%%Y-%%u')"
    else:
        date_expr = "DATE(si.posting_date)"

    conds = [
        "si.docstatus = 1",
        "si.status IN ('Paid', 'Return')",
        "si.posting_date BETWEEN %(from_date)s AND %(to_date)s",
    ]
    params = {"from_date": from_date, "to_date": to_date}

    if product and product != "all":
        conds.append(
            """
            (
                EXISTS (
                    SELECT 1 FROM `tabSubscription Plan` sp
                    WHERE (sp.name = si.custom_plan OR sp.plan_name = si.custom_plan)
                      AND sp.custom_project = %(project)s
                )
                OR EXISTS (
                    SELECT 1 FROM `tabSubscription Plan Detail` spd
                    INNER JOIN `tabSubscription Plan` sp ON (sp.name = spd.plan OR sp.plan_name = spd.plan)
                    WHERE spd.parent = si.subscription AND sp.custom_project = %(project)s
                )
            )
        """
        )
        params["project"] = product

    if team and team != "all":
        conds.append(
            """
            (
                si.owner = %(team)s
                OR EXISTS (
                    SELECT 1 FROM `tabCustomer` c
                    WHERE c.name = si.customer AND c.owner = %(team)s
                )
                OR EXISTS (
                    SELECT 1 FROM `tabCRM Deal` d
                    LEFT JOIN `tabCRM Lead` l ON l.name = d.lead
                    LEFT JOIN `tabCustomer` c ON c.name = si.customer
                    WHERE (d.erpnext_customer = si.customer OR c.crm_deal = d.name)
                      AND (
                        d.deal_owner = %(team)s
                        OR d.owner = %(team)s
                        OR l.lead_owner = %(team)s
                        OR l.owner = %(team)s
                      )
                )
            )
        """
        )
        params["team"] = team

    where = " AND ".join(conds)
    rows = frappe.db.sql(
        f"""
        SELECT {date_expr} AS label, si.name, si.grand_total, si.customer, si.subscription
        FROM `tabSales Invoice` si
        WHERE {where}
        ORDER BY si.posting_date ASC, si.creation ASC
    """,
        params,
        as_dict=True,
    )

    trend = defaultdict(lambda: {"new": 0.0, "renewal": 0.0})
    for row in rows:
        lbl = str(row.label)
        is_renewal = False
        if row.customer:
            earlier = frappe.db.count(
                "Sales Invoice",
                {
                    "customer": row.customer,
                    "docstatus": 1,
                    "status": ["in", ["Paid", "Return"]],
                    "posting_date": ["<", from_date],
                },
            )
            if earlier > 0:
                is_renewal = True
            else:
                first_inv = frappe.db.sql(
                    """
                    SELECT name FROM `tabSales Invoice`
                    WHERE customer = %(customer)s AND docstatus = 1 AND status IN ('Paid', 'Return')
                    ORDER BY posting_date ASC, creation ASC
                    LIMIT 1
                """,
                    {"customer": row.customer},
                    as_dict=True,
                )
                if first_inv and first_inv[0].name != row.name:
                    is_renewal = True

        if is_renewal:
            trend[lbl]["renewal"] += flt(row.grand_total)
        else:
            trend[lbl]["new"] += flt(row.grand_total)

    labels = sorted(trend.keys())
    return {
        "labels": labels,
        "new_revenue": [round(trend[l]["new"], 2) for l in labels],
        "renewal_revenue": [round(trend[l]["renewal"], 2) for l in labels],
    }


@frappe.whitelist()
def get_product_performance(period="last_30_days", team=None):
    from_date, to_date, _, _ = _get_date_range(period)

    # Get distinct projects from Subscription Plans
    projects = frappe.db.sql(
        """
        SELECT DISTINCT custom_project as project
        FROM `tabSubscription Plan`
        WHERE custom_project IS NOT NULL AND custom_project != ''
        ORDER BY custom_project
    """,
        as_dict=True,
    )

    result = []
    for p in projects:
        proj = p["project"]

        new_subs = _count_subscriptions(from_date, to_date, proj, None)
        active_subs = frappe.db.sql(
            """
            SELECT COUNT(DISTINCT s.name) as cnt FROM `tabSubscription` s
            WHERE s.status = 'Active' AND s.docstatus != 2
              AND EXISTS (
                SELECT 1 FROM `tabSubscription Plan Detail` spd
                INNER JOIN `tabSubscription Plan` sp ON (sp.name = spd.plan OR sp.plan_name = spd.plan)
                WHERE spd.parent = s.name AND sp.custom_project = %(proj)s
              )
        """,
            {"proj": proj},
            as_dict=True,
        )
        active_subs = cint(active_subs[0].cnt) if active_subs else 0
        expired = _count_expired_in_period(from_date, to_date, proj)
        rev = _get_revenue_split(from_date, to_date, proj, team)

        result.append(
            {
                "product": proj,
                "new_subs": new_subs,
                "new_revenue": rev["new_revenue"],
                "renewals": rev["renewals"],
                "renewal_revenue": rev["renewal_revenue"],
                "active_subs": active_subs,
                "expired": expired,
                "renewal_rate": rev["renewal_rate"],
                "total_revenue": round(rev["new_revenue"] + rev["renewal_revenue"], 2),
            }
        )

    result.sort(key=lambda x: x["total_revenue"], reverse=True)
    return result


def _get_crm_lead_users():
    users = frappe.db.sql(
        """
        SELECT DISTINCT u.name, u.full_name, u.email, u.role_profile_name
        FROM `tabUser` u
        LEFT JOIN `tabHas Role` hr ON hr.parent = u.name
        WHERE u.enabled = 1
          AND u.user_type = 'System User'
          AND (
            u.role_profile_name LIKE '%%CRM Lead%%'
            OR hr.role LIKE '%%CRM Lead%%'
          )
        ORDER BY u.full_name ASC, u.name ASC
    """,
        as_dict=True,
    )

    return users


@frappe.whitelist()
def get_sales_performance(period="last_30_days", product=None, team=None):
    from_date, to_date, _, _ = _get_date_range(period)

    users = _get_crm_lead_users()

    if team and team != "all":
        users = [u for u in users if u["name"] == team]

    rows = []
    for u in users:
        user_id = u["name"]
        user_disp = u["full_name"] or u["name"]

        # Count leads owned or created by user in period
        leads_res = frappe.db.sql(
            """
            SELECT COUNT(*) as cnt FROM `tabCRM Lead`
            WHERE (lead_owner = %(user)s OR owner = %(user)s)
              AND creation BETWEEN %(from_date)s AND %(to_date)s
        """,
            {"user": user_id, "from_date": from_date, "to_date": to_date},
            as_dict=True,
        )
        leads = cint(leads_res[0].cnt) if leads_res else 0

        conds = [
            "si.docstatus = 1",
            "si.status IN ('Paid', 'Return')",
            "si.posting_date BETWEEN %(from_date)s AND %(to_date)s",
            """(
                si.owner = %(user)s
                OR EXISTS (
                    SELECT 1 FROM `tabCustomer` c
                    WHERE c.name = si.customer AND c.owner = %(user)s
                )
                OR EXISTS (
                    SELECT 1 FROM `tabCRM Deal` d
                    LEFT JOIN `tabCRM Lead` l ON l.name = d.lead
                    LEFT JOIN `tabCustomer` c ON c.name = si.customer
                    WHERE (d.erpnext_customer = si.customer OR c.crm_deal = d.name)
                      AND (
                        d.deal_owner = %(user)s
                        OR d.owner = %(user)s
                        OR l.lead_owner = %(user)s
                        OR l.owner = %(user)s
                      )
                )
            )""",
        ]
        params = {"from_date": from_date, "to_date": to_date, "user": user_id}

        if product and product != "all":
            conds.append(
                """
                (
                    EXISTS (
                        SELECT 1 FROM `tabSubscription Plan` spl
                        WHERE (spl.name = si.custom_plan OR spl.plan_name = si.custom_plan)
                          AND spl.custom_project = %(project)s
                    )
                    OR EXISTS (
                        SELECT 1 FROM `tabSubscription Plan Detail` spd
                        INNER JOIN `tabSubscription Plan` sp ON (sp.name = spd.plan OR sp.plan_name = spd.plan)
                        WHERE spd.parent = si.subscription AND sp.custom_project = %(project)s
                    )
                )
            """
            )
            params["project"] = product

        where = " AND ".join(conds)
        paid_res = frappe.db.sql(
            f"""
            SELECT COUNT(DISTINCT si.customer) as cnt, COALESCE(SUM(si.grand_total), 0) as revenue
            FROM `tabSales Invoice` si WHERE {where}
        """,
            params,
            as_dict=True,
        )

        paid_customers = cint(paid_res[0].cnt) if paid_res else 0
        total_revenue = flt(paid_res[0].revenue) if paid_res else 0.0

        # Commission — gracefully skip if doctype doesn't exist
        commission = 0.0
        if frappe.db.table_exists("Sales Commission"):
            comm_res = frappe.db.sql(
                """
                SELECT COALESCE(SUM(incentive_amount), 0) as total
                FROM `tabSales Commission`
                WHERE sales_person = %(user)s AND docstatus = 1
                  AND posting_date BETWEEN %(from_date)s AND %(to_date)s
            """,
                {"user": user_id, "from_date": from_date, "to_date": to_date},
                as_dict=True,
            )
            commission = flt(comm_res[0].total) if comm_res else 0.0

        conversion_pct = round(paid_customers / leads * 100, 1) if leads else 0.0
        rows.append(
            {
                "salesperson": user_disp,
                "team": u.get("role_profile_name") or "CRM Lead Profile",
                "leads": leads,
                "paid_customers": paid_customers,
                "conversion_pct": conversion_pct,
                "total_revenue": round(total_revenue, 2),
                "commission": round(commission, 2),
            }
        )

    rows.sort(key=lambda x: x["total_revenue"], reverse=True)
    for i, r in enumerate(rows):
        r["rank"] = i + 1

    return rows[:20]


@frappe.whitelist()
def get_management_alerts(product=None, team=None):
    today = nowdate()
    alerts = []

    # 1. Subscriptions expired in last 3 days
    exp_3d = _count_expired_in_period(
        add_days(today, -3), today, product if product != "all" else None
    )
    if exp_3d > 0:
        val_conds = [
            "s.status = 'Expired'",
            "s.docstatus != 2",
            "s.end_date BETWEEN %(from_d)s AND %(to_d)s",
        ]
        val_params = {"from_d": add_days(today, -3), "to_d": today}
        if product and product != "all":
            val_conds.append(
                """
                EXISTS (
                    SELECT 1 FROM `tabSubscription Plan Detail` spd
                    INNER JOIN `tabSubscription Plan` sp ON (sp.name = spd.plan OR sp.plan_name = spd.plan)
                    WHERE spd.parent = s.name AND sp.custom_project = %(project)s
                )
            """
            )
            val_params["project"] = product
        val_where = " AND ".join(val_conds)
        val_res = frappe.db.sql(
            f"SELECT COALESCE(SUM(custom_cost), 0) as val FROM `tabSubscription` s WHERE {val_where}",
            val_params,
            as_dict=True,
        )
        val = flt(val_res[0].val) if val_res else 0
        currency = frappe.db.get_default("currency") or "USD"
        alerts.append(
            {
                "level": "critical",
                "title": f"{exp_3d} subscriptions expired in the last 3 days",
                "desc": f"Expected renewal value: {frappe.format_value(val, {'fieldtype': 'Currency', 'options': currency})}. Immediate follow-up required.",
                "link": "/app/subscription?status=Expired",
            }
        )

    # 2. Upcoming renewals next 7 days
    upcoming = frappe.db.sql(
        """
        SELECT COUNT(*) as cnt FROM `tabSubscription` s
        WHERE s.status = 'Active' AND s.docstatus != 2
          AND s.end_date BETWEEN %(today)s AND %(d7)s
    """,
        {"today": today, "d7": add_days(today, 7)},
        as_dict=True,
    )
    upcoming_cnt = cint(upcoming[0].cnt) if upcoming else 0
    if upcoming_cnt > 0:
        alerts.append(
            {
                "level": "warning",
                "title": f"{upcoming_cnt} subscriptions expire within the next 7 days",
                "desc": "Assign priority account managers to prevent churn.",
                "link": "/app/subscription?status=Active",
            }
        )

    # 3. Projects with renewal rate < 70% in last 30 days
    projects = frappe.db.sql(
        """
        SELECT DISTINCT custom_project as project FROM `tabSubscription Plan`
        WHERE custom_project IS NOT NULL AND custom_project != ''
    """,
        as_dict=True,
    )

    from_30 = add_days(today, -30)
    for p in projects:
        proj = p["project"]
        renewed = _count_subscriptions(from_30, today, proj, None)
        expired_p = _count_expired_in_period(from_30, today, proj)
        total = renewed + expired_p
        if total > 5:  # only alert if meaningful sample
            rate = round(renewed / total * 100, 1)
            if rate < 70:
                alerts.append(
                    {
                        "level": "critical",
                        "title": f"{proj} renewal rate is critically low at {rate}%",
                        "desc": "Investigate churn reasons and contact at-risk customers.",
                        "link": f"/app/subscription",
                    }
                )

    return alerts


@frappe.whitelist()
def get_filter_options():
    projects = frappe.db.sql(
        """
        SELECT DISTINCT custom_project as project FROM `tabSubscription Plan`
        WHERE custom_project IS NOT NULL AND custom_project != ''
        ORDER BY custom_project
    """,
        as_dict=True,
    )

    users = _get_crm_lead_users()
    teams = [
        {"name": u["name"], "full_name": u["full_name"] or u["name"]} for u in users
    ]

    statuses = frappe.db.sql(
        """
        SELECT DISTINCT status FROM `tabSubscription`
        WHERE status IS NOT NULL AND status != ''
        ORDER BY status ASC
    """,
        as_dict=True,
    )

    return {
        "projects": [r["project"] for r in projects],
        "teams": teams,
        "statuses": [r["status"] for r in statuses if r.get("status")],
    }


@frappe.whitelist()
def get_lead_conversion_metrics(product=None, team=None, status=None):
    today_dt = getdate(nowdate())
    today_start = f"{today_dt} 00:00:00"
    week_start = f"{today_dt - timedelta(days=today_dt.weekday())} 00:00:00"
    month_start = f"{date(today_dt.year, today_dt.month, 1)} 00:00:00"

    def get_lead_count(since_date):
        conds = ["creation >= %(since)s"]
        params = {"since": since_date}
        if team and team != "all":
            conds.append("(lead_owner = %(team)s OR owner = %(team)s)")
            params["team"] = team
        if product and product != "all":
            conds.append("custom_project = %(product)s")
            params["product"] = product
        where = " AND ".join(conds)
        res = frappe.db.sql(
            f"SELECT COUNT(*) as cnt FROM `tabCRM Lead` WHERE {where}",
            params,
            as_dict=True,
        )
        return cint(res[0].cnt) if res else 0

    def get_deal_conversion_count(since_date):
        conds = ["d.creation >= %(since)s", "d.lead IS NOT NULL AND d.lead != ''"]
        params = {"since": since_date}
        if team and team != "all":
            conds.append(
                """(
                d.deal_owner = %(team)s OR d.owner = %(team)s OR EXISTS (
                    SELECT 1 FROM `tabCRM Lead` l WHERE l.name = d.lead AND (l.lead_owner = %(team)s OR l.owner = %(team)s)
                )
            )"""
            )
            params["team"] = team
        if product and product != "all":
            conds.append("d.custom_project = %(product)s")
            params["product"] = product
        if status and status != "all":
            conds.append("d.status = %(status)s")
            params["status"] = status
        where = " AND ".join(conds)
        res = frappe.db.sql(
            f"SELECT COUNT(*) as cnt FROM `tabCRM Deal` d WHERE {where}",
            params,
            as_dict=True,
        )
        return cint(res[0].cnt) if res else 0

    def get_customer_count(since_date):
        conds = ["c.creation >= %(since)s"]
        params = {"since": since_date}
        if team and team != "all":
            conds.append(
                """(
                c.owner = %(team)s OR EXISTS (
                    SELECT 1 FROM `tabCRM Deal` d WHERE (d.erpnext_customer = c.name OR c.crm_deal = d.name)
                    AND (d.deal_owner = %(team)s OR d.owner = %(team)s)
                )
            )"""
            )
            params["team"] = team
        if product and product != "all":
            conds.append(
                """(
                c.custom_project = %(product)s OR EXISTS (
                    SELECT 1 FROM `tabCRM Deal` d WHERE (d.erpnext_customer = c.name OR c.crm_deal = d.name)
                    AND d.custom_project = %(product)s
                )
            )"""
            )
            params["product"] = product
        where = " AND ".join(conds)
        res = frappe.db.sql(
            f"SELECT COUNT(*) as cnt FROM `tabCustomer` c WHERE {where}",
            params,
            as_dict=True,
        )
        return cint(res[0].cnt) if res else 0

    return {
        "leads": {
            "today": get_lead_count(today_start),
            "this_week": get_lead_count(week_start),
            "this_month": get_lead_count(month_start),
        },
        "deals": {
            "today": get_deal_conversion_count(today_start),
            "this_week": get_deal_conversion_count(week_start),
            "this_month": get_deal_conversion_count(month_start),
        },
        "customers": {
            "today": get_customer_count(today_start),
            "this_week": get_customer_count(week_start),
            "this_month": get_customer_count(month_start),
        },
    }


@frappe.whitelist()
def send_kpi_report_email(
    recipients,
    period="last_30_days",
    product="all",
    team="all",
    status="all",
    message="",
):
    if isinstance(recipients, str):
        recipients = [r.strip() for r in recipients.split(",") if r.strip()]

    if not recipients:
        frappe.throw(
            frappe._("Please provide at least one valid recipient email address.")
        )

    kpis = get_top_kpis(period=period, product=product, team=team, status=status)
    pipeline = get_lead_conversion_metrics(product=product, team=team, status=status)

    currency = kpis.get("currency") or "USD"
    subs = kpis.get("subscriptions", {})
    fp = kpis.get("first_payment", {})
    rn = kpis.get("renewal", {})
    tot = kpis.get("total_collection", {})

    period_title = period.replace("_", " ").title()

    email_html = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 650px; margin: 0 auto; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 24px; color: #1f2937;">
        <div style="border-bottom: 2px solid #6366f1; padding-bottom: 12px; margin-bottom: 20px;">
            <h2 style="margin: 0; color: #111827; font-size: 20px; font-weight: 700;">SaaS Sales Executive KPI Report</h2>
            <p style="margin: 4px 0 0 0; color: #6b7280; font-size: 13px;">Reporting Period: <strong>{period_title}</strong> | Product: <strong>{product.title()}</strong></p>
        </div>

        {f'<div style="background: #f3f4f6; padding: 12px 16px; border-radius: 8px; font-size: 13px; color: #374151; margin-bottom: 20px;"><strong>Note:</strong> {frappe.utils.escape_html(message)}</div>' if message else ''}

        <h3 style="font-size: 14px; color: #374151; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Financial & Subscription KPIs</h3>
        <table style="width: 100%; border-collapse: separate; border-spacing: 10px; margin-bottom: 20px;">
            <tr>
                <td style="width: 50%; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 10px; padding: 14px; vertical-align: top;">
                    <div style="font-size: 11px; font-weight: 700; color: #1d4ed8; text-transform: uppercase;">New Subscriptions</div>
                    <div style="font-size: 24px; font-weight: 800; color: #1e40af; margin: 4px 0;">{subs.get('current', 0)}</div>
                    <div style="font-size: 12px; color: #3b82f6;">Today: {subs.get('today', 0)} | Week: {subs.get('this_week', 0)}</div>
                </td>
                <td style="width: 50%; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 10px; padding: 14px; vertical-align: top;">
                    <div style="font-size: 11px; font-weight: 700; color: #047857; text-transform: uppercase;">First Payment Revenue</div>
                    <div style="font-size: 24px; font-weight: 800; color: #065f46; margin: 4px 0;">{frappe.format_value(fp.get('revenue', 0), {'fieldtype': 'Currency', 'options': currency})}</div>
                    <div style="font-size: 12px; color: #10b981;">Paying Customers: {fp.get('paying_customers', 0)}</div>
                </td>
            </tr>
            <tr>
                <td style="width: 50%; background: #f5f3ff; border: 1px solid #ddd6fe; border-radius: 10px; padding: 14px; vertical-align: top;">
                    <div style="font-size: 11px; font-weight: 700; color: #6d28d9; text-transform: uppercase;">Renewal Revenue</div>
                    <div style="font-size: 24px; font-weight: 800; color: #5b21b6; margin: 4px 0;">{frappe.format_value(rn.get('revenue', 0), {'fieldtype': 'Currency', 'options': currency})}</div>
                    <div style="font-size: 12px; color: #8b5cf6;">Renewals: {rn.get('renewals', 0)} ({rn.get('renewal_rate_pct', 0)}%)</div>
                </td>
                <td style="width: 50%; background: #fffbeb; border: 1px solid #fde68a; border-radius: 10px; padding: 14px; vertical-align: top;">
                    <div style="font-size: 11px; font-weight: 700; color: #b45309; text-transform: uppercase;">Total Collection</div>
                    <div style="font-size: 24px; font-weight: 800; color: #92400e; margin: 4px 0;">{frappe.format_value(tot.get('revenue', 0), {'fieldtype': 'Currency', 'options': currency})}</div>
                    <div style="font-size: 12px; color: #f59e0b;">Growth Pct: {tot.get('change_pct', 0)}%</div>
                </td>
            </tr>
        </table>

        <h3 style="font-size: 14px; color: #374151; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Pipeline & Acquisition Summary</h3>
        <table style="width: 100%; border-collapse: collapse; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 20px;">
            <thead>
                <tr style="background: #f9fafb; border-bottom: 1px solid #e5e7eb;">
                    <th style="padding: 10px 14px; text-align: left; font-size: 12px; font-weight: 700; color: #4b5563;">Metric Category</th>
                    <th style="padding: 10px 14px; text-align: center; font-size: 12px; font-weight: 700; color: #4b5563;">Today</th>
                    <th style="padding: 10px 14px; text-align: center; font-size: 12px; font-weight: 700; color: #4b5563;">This Week</th>
                    <th style="padding: 10px 14px; text-align: center; font-size: 12px; font-weight: 700; color: #4b5563;">This Month</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid #f3f4f6;">
                    <td style="padding: 10px 14px; font-size: 13px; font-weight: 600; color: #111827;">Leads Created</td>
                    <td style="padding: 10px 14px; text-align: center; font-size: 13px;">{pipeline.get('leads', {}).get('today', 0)}</td>
                    <td style="padding: 10px 14px; text-align: center; font-size: 13px;">{pipeline.get('leads', {}).get('this_week', 0)}</td>
                    <td style="padding: 10px 14px; text-align: center; font-size: 13px; font-weight: 700; color: #4f46e5;">{pipeline.get('leads', {}).get('this_month', 0)}</td>
                </tr>
                <tr style="border-bottom: 1px solid #f3f4f6;">
                    <td style="padding: 10px 14px; font-size: 13px; font-weight: 600; color: #111827;">Leads Converted to Deals</td>
                    <td style="padding: 10px 14px; text-align: center; font-size: 13px;">{pipeline.get('deals', {}).get('today', 0)}</td>
                    <td style="padding: 10px 14px; text-align: center; font-size: 13px;">{pipeline.get('deals', {}).get('this_week', 0)}</td>
                    <td style="padding: 10px 14px; text-align: center; font-size: 13px; font-weight: 700; color: #4f46e5;">{pipeline.get('deals', {}).get('this_month', 0)}</td>
                </tr>
                <tr>
                    <td style="padding: 10px 14px; font-size: 13px; font-weight: 600; color: #111827;">Customers Created</td>
                    <td style="padding: 10px 14px; text-align: center; font-size: 13px;">{pipeline.get('customers', {}).get('today', 0)}</td>
                    <td style="padding: 10px 14px; text-align: center; font-size: 13px;">{pipeline.get('customers', {}).get('this_week', 0)}</td>
                    <td style="padding: 10px 14px; text-align: center; font-size: 13px; font-weight: 700; color: #4f46e5;">{pipeline.get('customers', {}).get('this_month', 0)}</td>
                </tr>
            </tbody>
        </table>

        <div style="font-size: 11px; color: #9ca3af; text-align: center; border-top: 1px solid #f3f4f6; padding-top: 12px; margin-top: 20px;">
            Generated automatically from SaaS Sales Dashboard on {frappe.utils.now_datetime().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
    """

    frappe.sendmail(
        recipients=recipients,
        subject=f"SaaS Sales KPI Report - {period_title}",
        message=email_html,
        now=True,
    )
    return True
