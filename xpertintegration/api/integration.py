import json
import re
import base64
import mimetypes
import os
import requests

import frappe
from frappe.utils import (
    cint,
    flt,
    getdate,
    today,
    format_date,
)
from dateutil.relativedelta import relativedelta

from erpnext.accounts.doctype.subscription.subscription import (
    Subscription,
    get_prorata_factor,
)
from erpnext.accounts.doctype.subscription_plan.subscription_plan import get_plan_rate
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
    get_accounting_dimensions,
)


# SECTION 1: DYNAMIC CONFIGURATION
def get_integration_logger():
    return frappe.logger("xpertintegration")


def get_lead_to_deal_mapping():
    return [
        {"source": "custom_project", "target": "custom_project"},
        {"source": "custom_plan", "target": "custom_plan"},
        {"source": "territory", "target": "territory"},
        {"source": "custom_sub_domain", "target": "custom_sub_domain"},
        {"source": "custom_no_of_connections", "target": "custom_no_of_connections"},
        {"source": "custom_sample_data", "target": "custom_sample_data"},
        {"source": "custom_assigned_to", "target": "custom_assigned_to"},
        {"source": "custom_remarks", "target": "custom_remarks"},
        {"source": "custom_company_code", "target": "custom_company_code"},
        {"source": "company_code", "target": "company_code"},
        {"source": "custom_posting_date", "target": "custom_posting_date"},
        {"source": "custom_due_date", "target": "custom_due_date"},
        {"source": "custom_password", "target": "custom_password"},
        {
            "source": "custom_activation_start_date",
            "target": "custom_activation_start_date",
        },
        {
            "source": "custom_activation_end_date",
            "target": "custom_activation_end_date",
        },
    ]


def get_deal_win_validation_rules():
    return {
        "mandatory_fields": [
            "first_name",
            "email",
            "mobile_no",
            "territory",
            "custom_sub_domain",
            "custom_plan",
            "custom_password",
            "custom_activation_start_date",
            "custom_activation_end_date",
        ],
        "error_message": "Please fill the following mandatory fields before winning the deal: {fields}",
    }


def get_customer_deal_sync_fields():
    return [
        "custom_password",
        "custom_plan",
        "territory",
        "custom_sub_domain",
        "custom_sample_data",
        "custom_activation_start_date",
        "custom_activation_end_date",
        "custom_sell_only_products",
        "custom_project",
    ]


def get_payment_validation_config():
    return {
        "fields": ["custom_amount", "custom_posting_date", "custom_due_date"],
        "error_message": "The following payment fields are mandatory when Company Code is provided: {fields}",
    }


def get_mobile_validation_config():
    return {
        "regex": r"^03\d{9}$",
        "error_message": "Phone number must be exactly 11 digits and start with 03 (e.g., 03000000000).",
        "check_duplicate": True,
    }


def get_broadcast_config():
    return {
        # If True, strips 'name' so remote creates instead of updating.
        # Set to False once the remote supports upsert by a sync key.
        "strip_name_for_remote_create": False,
    }


STATUS_ICONS = {
    "Initiated": "🚀",
    "Ringing": "📳",
    "In Progress": "🔄",
    "Completed": "✅",
    "Failed": "❌",
    "Busy": "🔴",
    "No Answer": "📵",
    "Queued": "⏳",
    "Canceled": "🚫",
}


# SECTION 2: UTILITY HELPERS
def _safe_get_doc(doctype, name, log_title=None):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        if log_title:
            get_integration_logger().warning(f"{log_title}: {doctype} {name} not found")
        return None
    except Exception:
        if log_title:
            frappe.log_error(title=log_title, message=frappe.get_traceback())
        return None


def _sync_doc_fields(source_doc, target_doc, field_map):
    for rule in field_map:
        if isinstance(rule, str):
            sf = tf = rule
        else:
            sf, tf = rule.get("source"), rule.get("target")
        if not target_doc.get(tf) and source_doc.get(sf) is not None:
            target_doc.set(tf, source_doc.get(sf))


def _compute_doc_amount(doc):
    from frappe.utils import flt

    plan_amount = flt(doc.get("custom_sale_price"))

    addons_amount = 0
    for addon in doc.get("custom_addons_table", []):
        addons_amount += flt(addon.get("amount"))

    return plan_amount + addons_amount


def _calculate_subscription_end_date(plan_name, start_date, end_date):
    try:
        plan_doc = frappe.get_doc("Subscription Plan", plan_name)
        interval = plan_doc.billing_interval
        interval_count = plan_doc.billing_interval_count or 1
        start_dt = getdate(start_date or today())

        if interval == "Year":
            min_end = start_dt + relativedelta(years=interval_count)
        elif interval == "Quarter":
            min_end = start_dt + relativedelta(months=3 * interval_count)
        elif interval == "Month":
            min_end = start_dt + relativedelta(months=interval_count)
        else:
            min_end = start_dt + relativedelta(months=1)

        if end_date:
            actual_end = getdate(end_date)
            if actual_end < min_end:
                end_date = min_end.strftime("%Y-%m-%d")
        else:
            end_date = min_end.strftime("%Y-%m-%d")

    except Exception:
        start_dt = getdate(start_date or today())
        end_date = (start_dt + relativedelta(years=1)).strftime("%Y-%m-%d")

    return end_date


def _clean_child_table_rows(rows):
    if not isinstance(rows, list):
        return rows
    system_keys = {
        "name",
        "creation",
        "modified",
        "modified_by",
        "owner",
        "__unsaved",
        "__islocal",
        "parent",
        "parentfield",
        "parenttype",
        "idx",
        "docstatus",
    }
    for row in rows:
        if isinstance(row, dict):
            for k in system_keys:
                row.pop(k, None)
    return rows


def _clean_payload_timestamps(payload):
    for k in ["creation", "modified", "modified_by", "owner"]:
        payload.pop(k, None)
    return payload


def get_call_log_summary(call_type_str, date_str, status):
    icon = STATUS_ICONS.get(status, "")
    status_display = f"{icon} {status}".strip() if status else ""
    if status_display:
        return f"{call_type_str} • {date_str} • {status_display}"
    return f"{call_type_str} • {date_str}"


# SECTION 3: PROJECT SETTINGS & API
def get_project_settings(project, throw=True):
    if not project:
        if throw:
            frappe.throw("Project is required to get integration settings.")
        return None, None

    cache_key = f"xpertintegration:project_settings:{project}"
    cached = frappe.cache().get_value(cache_key)
    if cached:
        return cached

    rows = frappe.db.sql(
        """
        SELECT project, base_url, api_url, api_key, api_secret
        FROM `tabXpertIntegration Setting Table`
        WHERE project = %s
        LIMIT 1
        """,
        (project,),
        as_dict=True,
    )

    if not rows:
        if throw:
            frappe.throw(f"No integration settings found for project '{project}'.")
        return None, None

    setting = rows[0]
    base_url = (setting.get("base_url") or "").rstrip("/")
    api_key = setting.get("api_key")
    api_secret = setting.get("api_secret")
    api_endpoint = (setting.get("api_url") or "").strip()

    if not base_url or not api_key or not api_secret:
        if throw:
            frappe.throw(
                f"Base URL or API Key/Secret is missing for project '{project}'."
            )
        return None, None

    if not api_endpoint:
        if throw:
            frappe.throw(f"API URL is not configured for project '{project}'.")
        return None, None

    if not api_endpoint.startswith("/"):
        api_endpoint = "/" + api_endpoint

    target_url = f"{base_url}{api_endpoint}"
    headers = {
        "Authorization": f"token {api_key}:{api_secret}",
        "Content-Type": "application/json",
    }

    result = (target_url, headers)
    frappe.cache().set_value(cache_key, result, expires_in_sec=300)
    return result


def send_api_request(
    target_url, headers, payload, source_doctype=None, source_docname=None
):
    logger = get_integration_logger()
    try:
        response = requests.post(
            target_url,
            headers=headers,
            json={"payload": payload},
            timeout=60,
        )
        response.raise_for_status()

        try:
            resp_json = response.json()
            if source_doctype and source_docname and isinstance(resp_json, dict):
                callback_data = resp_json.get("message", {}).get("callback_data")
                if isinstance(callback_data, dict):
                    frappe.db.set_value(source_doctype, source_docname, callback_data)
                    # NOTE: Removed manual frappe.db.commit() — let Frappe handle the transaction boundary.
            return {"status": "success", "data": resp_json}
        except ValueError:
            return {"status": "success", "text": response.text}

    except requests.exceptions.HTTPError:
        err_msg = (
            f"HTTP Error {response.status_code} from {target_url}\n"
            f"Response: {response.text}\n"
            f"Payload: {json.dumps(payload, default=str)}"
        )
        logger.error(err_msg)
        return {
            "status": "failed",
            "error": response.text,
            "status_code": response.status_code,
        }
    except requests.exceptions.RequestException as e:
        err_msg = (
            f"Network Exception connecting to {target_url}\n"
            f"Error: {str(e)}\n"
            f"Payload: {json.dumps(payload, default=str)}"
        )
        logger.error(err_msg)
        return {"status": "failed", "error": str(e)}


# SECTION 4: VALIDATION ENGINE
@frappe.whitelist()
def validate_crm_deal(doc, method=None):
    # 1. Auto-calculate amount
    doc.custom_amount = _compute_doc_amount(doc)

    # 2. Lock Won deals
    if not doc.is_new():
        old_status = frappe.db.get_value("CRM Deal", doc.name, "status")
        if old_status == "Won":
            frappe.throw(
                "This Deal has already been marked as 'Won' and cannot be edited."
            )

    # 3. Payment fields when company code exists
    company_code = doc.get("custom_company_code") or doc.get("company_code")
    if company_code and not doc.is_new():
        config = get_payment_validation_config()
        missing = [f for f in config["fields"] if not doc.get(f)]
        if missing:
            labels = [doc.meta.get_label(f) for f in missing]
            frappe.throw(config["error_message"].format(fields=", ".join(labels)))

    # 4. Win conditions
    if doc.status == "Won":
        _validate_deal_win_conditions(doc)

    # 5. Broadcast as Customer if In Trial
    send_trial_deal_as_customer(doc)


def _validate_deal_win_conditions(doc):
    project = doc.get("custom_project")
    project_label = doc.meta.get_label("custom_project") or "Project"
    if not project:
        frappe.throw(
            f"Please fill the following mandatory fields before winning the deal: {project_label}"
        )

    # Validate project settings exist and are complete
    target_url, headers = get_project_settings(project, throw=False)
    if not target_url:
        # Settings incomplete — get_project_settings already threw or returned None.
        # We do a soft check here to give a cleaner message.
        setting = frappe.db.get_value(
            "XpertIntegration Setting Table",
            {"project": project},
            ["base_url", "api_url", "api_key", "api_secret"],
            as_dict=True,
        )
        if not setting:
            frappe.throw(f"Project settings for '{project}' are missing.")
        missing = []
        if not setting.get("base_url"):
            missing.append("Base URL")
        if not setting.get("api_url"):
            missing.append("API URL")
        if not setting.get("api_key"):
            missing.append("API Key")
        if not setting.get("api_secret"):
            missing.append("API Secret")
        if missing:
            frappe.throw(
                f"Project settings for '{project}' are incomplete. Missing: {', '.join(missing)}"
            )

    # Backfill email / mobile from lead
    if not doc.email and doc.lead:
        doc.email = frappe.db.get_value("CRM Lead", doc.lead, "email")
    if not doc.mobile_no and doc.lead:
        doc.mobile_no = frappe.db.get_value("CRM Lead", doc.lead, "mobile_no")

    # Dynamic mandatory fields
    rules = get_deal_win_validation_rules()
    missing_fields = [f for f in rules["mandatory_fields"] if not doc.get(f)]
    if missing_fields:
        labels = [doc.meta.get_label(f) for f in missing_fields]
        frappe.throw(rules["error_message"].format(fields=", ".join(labels)))


def send_trial_deal_as_customer(doc):
    if doc.status == "In Trial" and not doc.get("custom_company_code"):
        # Validate fields before proceeding
        project_label = doc.meta.get_label("custom_project") or "Project"
        if not doc.get("custom_project"):
            frappe.throw(
                f"Please fill the following mandatory fields before changing the status to In Trial: {project_label}"
            )

        rules = get_deal_win_validation_rules()
        missing_fields = [f for f in rules["mandatory_fields"] if not doc.get(f)]
        if missing_fields:
            labels = [doc.meta.get_label(f) for f in missing_fields]
            frappe.throw(
                f"Please fill the following mandatory fields before changing the status to In Trial: {', '.join(labels)}"
            )

        payload = frappe.parse_json(doc.as_json())
        payload["doctype"] = "Customer"

        project_val = doc.get("custom_project")
        if not project_val:
            return

        project_id = (
            frappe.db.get_value("Project", {"project_name": project_val}, "name")
            or frappe.db.get_value("Project", project_val, "name")
            or project_val
        )
        if not project_id:
            return

        project_name = (
            frappe.db.get_value("Project", project_id, "project_name") or project_id
        )

        payload = _build_broadcast_payload(payload, project_id, project_name)

        try:
            frappe.enqueue(
                "xpertintegration.api.integration._execute_broadcast",
                queue="long",
                payload=payload,
                doctype="Customer",
                docname=doc.name,
                project_id=project_id,
                source_doctype=doc.doctype,
                source_docname=doc.name,
            )
        except Exception:
            frappe.log_error(
                title=f"Broadcast Enqueue Failed: {doc.doctype} {doc.name} as Customer",
                message=frappe.get_traceback(),
            )


@frappe.whitelist()
def validate_crm_fields(doc, method=None):
    # Duplicate company check
    if doc.is_new() and doc.get("organization"):
        existing = frappe.db.exists("Customer", {"customer_name": doc.organization})
        if existing:
            frappe.throw(
                f"A Customer with the company name '{doc.organization}' already exists in the system."
            )

    # Mobile validation
    if doc.get("mobile_no"):
        config = get_mobile_validation_config()
        mobile_str = str(doc.mobile_no).strip()
        if not re.match(config["regex"], mobile_str):
            frappe.throw(config["error_message"])

        if config.get("check_duplicate"):
            existing = frappe.db.exists(
                "CRM Lead", {"mobile_no": mobile_str, "name": ("!=", doc.name)}
            )
            if existing:
                frappe.throw(
                    f"A Lead with this mobile number already exists ({existing})."
                )

    # Referral code resolution
    ref_code = doc.get("custom_referral_code") or doc.get("referral_code")
    if ref_code:
        user_with_code = frappe.db.get_value(
            "User Referral Code", {"referral_code": ref_code}, "user"
        )
        if user_with_code:
            doc.lead_owner = user_with_code


@frappe.whitelist()
def validate_sales_invoice(doc, method=None):
    if doc.get("subscription") and doc.get("customer"):
        cust = frappe.db.get_value(
            "Customer", doc.customer, ["custom_project", "crm_deal"], as_dict=True
        )
        if cust:
            if cust.custom_project and not doc.get("project"):
                doc.project = cust.custom_project
            if cust.crm_deal and not doc.get("custom_crm_deal"):
                doc.custom_crm_deal = cust.crm_deal


# SECTION 5: CRM LEAD HOOKS
@frappe.whitelist()
def after_crm_lead_insert(doc, method=None):
    if doc.get("custom_assigned_to"):
        _create_follow_up_task("CRM Lead", doc.name, doc.custom_assigned_to)

    if doc.get("custom_company_code") and not doc.get("is_converted"):
        _auto_convert_lead_to_deal(doc)


def _create_follow_up_task(ref_doctype, ref_name, assigned_to):
    existing = frappe.db.exists(
        "CRM Task",
        {"reference_doctype": ref_doctype, "reference_docname": ref_name},
    )
    if existing:
        return

    try:
        task = frappe.get_doc(
            {
                "doctype": "CRM Task",
                "title": f"Follow up on {ref_doctype.split()[-1]}: {ref_name}",
                "assigned_to": assigned_to,
                "status": "Todo",
                "reference_doctype": ref_doctype,
                "reference_docname": ref_name,
                "description": f"Automatically created task for {ref_doctype} {ref_name}",
            }
        )
        task.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(
            title=f"Task Creation Failed: {ref_doctype} {ref_name}",
            message=frappe.get_traceback(),
        )


def _auto_convert_lead_to_deal(lead_doc):
    existing_deal = frappe.db.exists("CRM Deal", {"lead": lead_doc.name})
    if existing_deal:
        return

    deal_fields = {
        "custom_create_company": 1,
        "status": "In Trial",
        "custom_posting_date": frappe.utils.today(),
        "custom_due_date": frappe.utils.add_days(frappe.utils.today(), 5),
    }

    # Apply dynamic field mapping
    mapping = get_lead_to_deal_mapping()
    for rule in mapping:
        val = lead_doc.get(rule["source"])
        if val:
            deal_fields[rule["target"]] = val

    # Computed amount
    amount = _compute_doc_amount(lead_doc)
    if amount:
        deal_fields["custom_amount"] = amount

    # Special fields not in generic map
    if lead_doc.get("email"):
        deal_fields["primary_email"] = lead_doc.email

    if lead_doc.get("custom_addons_table"):
        deal_fields["custom_addons_table"] = [
            {
                "add_on": row.add_on,
                "description": row.description,
                "amount": row.amount,
            }
            for row in lead_doc.custom_addons_table
        ]

    try:
        lead_doc.convert_to_deal(deal=deal_fields)
    except Exception:
        frappe.log_error(
            title=f"Lead Conversion Failed: {lead_doc.name}",
            message=frappe.get_traceback(),
        )


@frappe.whitelist()
def update_lead_last_call_log(doc, method=None):
    if doc.reference_doctype == "CRM Lead" and doc.reference_docname:
        call_type = "Inbound Call" if doc.type == "Incoming" else "Outbound Call"
        date_str = format_date(doc.creation, "MMM dd, yyyy")
        summary = get_call_log_summary(call_type, date_str, doc.status or "")
        frappe.db.set_value(
            "CRM Lead", doc.reference_docname, "custom_last_call_log", summary
        )


@frappe.whitelist()
def sync_all_leads_last_call_log():
    logs = frappe.get_all(
        "CRM Call Log",
        filters={"reference_doctype": "CRM Lead"},
        fields=["reference_docname", "type", "status", "creation"],
        order_by="creation asc",
    )

    if not logs:
        return {"updated": 0}

    # Last-one-wins per lead (ascending order guarantees last is latest)
    latest = {}
    for log in logs:
        if log.reference_docname:
            latest[log.reference_docname] = log

    if not latest:
        return {"updated": 0}

    cases = []
    values = []
    for lead_name, log in latest.items():
        call_type = "Inbound Call" if log.type == "Incoming" else "Outbound Call"
        date_str = format_date(log.creation, "MMM dd, yyyy")
        summary = get_call_log_summary(call_type, date_str, log.status or "")
        cases.append("WHEN %s THEN %s")
        values.extend([lead_name, summary])

    names = list(latest.keys())
    values.extend(names)

    sql = f"""
        UPDATE `tabCRM Lead`
        SET custom_last_call_log = CASE name
            {" ".join(cases)}
        END
        WHERE name IN ({','.join(['%s'] * len(names))})
    """

    frappe.db.sql(sql, values)
    return {"updated": len(names)}


# SECTION 6: CRM DEAL HOOKS
@frappe.whitelist()
def after_crm_deal_insert(doc, method=None):
    if not doc.get("custom_assigned_to"):
        return

    try:
        task = frappe.get_doc(
            {
                "doctype": "CRM Task",
                "title": f"Follow up on Deal: {doc.name}",
                "assigned_to": doc.custom_assigned_to,
                "status": "Todo",
                "reference_doctype": "CRM Deal",
                "reference_docname": doc.name,
                "description": f"Automatically created task for Deal {doc.name}",
            }
        )
        task.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(
            title=f"Deal Task Creation Failed: {doc.name}",
            message=frappe.get_traceback(),
        )


@frappe.whitelist()
def broadcast_crm_deal(doc, method=None):
    is_trial = doc.get("status") and doc.status == "In Trial"
    has_payment = doc.get("custom_amount")

    if not is_trial and not has_payment:
        return

    if doc.get("status") == "Won":
        return

    broadcast_crm_document(doc, method)


# SECTION 7: CUSTOMER & SUBSCRIPTION HOOKS
@frappe.whitelist()
def before_customer_insert(doc, method=None):
    if not doc.crm_deal:
        return

    deal = _safe_get_doc("CRM Deal", doc.crm_deal, log_title="Customer Pre-Insert Sync")
    if not deal:
        return

    # Dynamic field sync
    _sync_doc_fields(deal, doc, get_customer_deal_sync_fields())

    # Special name / contact fields
    if not doc.get("first_name") and deal.get("first_name"):
        doc.first_name = deal.first_name
    if not doc.get("last_name") and deal.get("last_name"):
        doc.last_name = deal.last_name
    if not doc.get("email_id") and deal.get("email"):
        doc.email_id = deal.email
    if not doc.get("mobile_no") and deal.get("mobile_no"):
        doc.mobile_no = deal.mobile_no

    if not doc.get("custom_project_company"):
        code = deal.get("custom_company_code") or deal.get("company_code")
        if code:
            doc.custom_project_company = code


@frappe.whitelist()
def broadcast_customer_company(doc, method=None):
    try:
        frappe.log_error(
            title="Customer-Company Debug: Start",
            message=f"Doc: {doc.name}, Company Code: {doc.get('custom_project_company')}",
        )

        if doc.get("custom_project_company"):
            payload = frappe.parse_json(doc.as_json())
            payload["doctype"] = "Customer-Company"

            project_val = doc.get("custom_project")
            if not project_val and doc.get("crm_deal"):
                project_val = frappe.db.get_value(
                    "CRM Deal", doc.crm_deal, "custom_project"
                )

            if not project_val:
                frappe.log_error(
                    title="Customer-Company Debug: Abort",
                    message="No project_val found",
                )
                return

            project_id = (
                frappe.db.get_value("Project", {"project_name": project_val}, "name")
                or frappe.db.get_value("Project", project_val, "name")
                or project_val
            )
            if not project_id:
                frappe.log_error(
                    title="Customer-Company Debug: Abort",
                    message=f"No project_id found for project_val: {project_val}",
                )
                return

            project_name = (
                frappe.db.get_value("Project", project_id, "project_name") or project_id
            )

            payload = _build_broadcast_payload(payload, project_id, project_name)
            payload["doctype"] = "Customer-Company"

            doc_name = doc.name or "New Customer"
            target_url, headers = get_project_settings(project_id, throw=False)
            if not target_url:
                frappe.log_error(
                    title="Customer-Company Debug: Abort",
                    message=f"No target_url found for project: {project_id}",
                )
                return

            frappe.log_error(
                title="Customer-Company Debug: Request",
                message=f"URL: {target_url}\nPayload: {payload}",
            )

            response = send_api_request(
                target_url,
                headers,
                payload,
                source_doctype=doc.doctype,
                source_docname=doc_name,
            )

            frappe.log_error(
                title="Customer-Company Debug: Response", message=str(response)
            )

            if response.get("status") == "success":
                data = response.get("data", {})
                message = data.get("message", {})

                callback_data = {}
                if isinstance(message, dict):
                    callback_data = message.get("callback_data", {})

                returned_company = callback_data.get("custom_project_company")
                if not returned_company:
                    frappe.throw("Against this project no company found")
            else:
                frappe.throw(
                    f"Failed to verify company in project: {response.get('error')}"
                )
    except Exception:
        frappe.log_error(
            title="Customer-Company Debug: Exception", message=frappe.get_traceback()
        )
        raise


@frappe.whitelist()
def create_subscription(doc, method=None):
    if getattr(doc.flags, "integration_broadcasted", False):
        return

    if not doc.crm_deal or not doc.get("custom_plan"):
        return

    if frappe.db.exists("Subscription", {"party": doc.name}):
        return

    company = frappe.defaults.get_user_default("Company") or frappe.db.get_value(
        "Company"
    )
    start_date = doc.get("custom_activation_start_date")
    start_dt = getdate(start_date or today())
    end_date = (start_dt + relativedelta(years=1)).strftime("%Y-%m-%d")

    try:
        deal_doc = None
        if doc.crm_deal:
            deal_doc = _safe_get_doc("CRM Deal", doc.crm_deal)

        plan_entry = {"plan": doc.custom_plan, "qty": 1}
        if deal_doc and deal_doc.get("custom_sale_price"):
            plan_entry["custom_cost"] = deal_doc.custom_sale_price

        plans_list = [plan_entry]

        if deal_doc:
            for addon in deal_doc.get("custom_addons_table", []):
                if addon.add_on:
                    addon_entry = {"plan": addon.add_on, "qty": 1}
                    if addon.get("amount"):
                        addon_entry["custom_cost"] = addon.amount
                    plans_list.append(addon_entry)

        sub = frappe.get_doc(
            {
                "doctype": "Subscription",
                "party_type": "Customer",
                "party": doc.name,
                "company": company,
                "plans": plans_list,
                "start_date": start_date or today(),
                "end_date": end_date,
                "generate_invoice_at": "Beginning of the current subscription period",
                "submit_invoice": 1,
                "status": "Active",
                "custom_project_company": doc.custom_project_company,
                "custom_project_subscription": deal_doc.custom_project if deal_doc else None,
            }
        )
        sub.insert(ignore_permissions=True)
        sub.process()

        # Create Payment Entry if Paid Amount exists in CRM Deal
        if deal_doc and deal_doc.get("custom_paid_amount"):
            paid_amount = deal_doc.custom_paid_amount

            invoices = frappe.get_all(
                "Sales Invoice",
                filters={"subscription": sub.name},
                limit=1,
            )

            if invoices:
                inv_name = invoices[0].name
                # Pass CRM Deal to Sales Invoice
                frappe.db.set_value(
                    "Sales Invoice", inv_name, "custom_crm_deal", doc.crm_deal
                )

                try:
                    from erpnext.accounts.doctype.payment_entry.payment_entry import (
                        get_payment_entry,
                    )

                    pe = get_payment_entry("Sales Invoice", inv_name, bank_account=None)
                    pe.paid_amount = paid_amount
                    pe.received_amount = paid_amount

                    for ref in pe.references:
                        if ref.reference_name == inv_name:
                            ref.allocated_amount = paid_amount

                    pe.insert(ignore_permissions=True)
                    pe.submit()

                    # Check the updated Sales Invoice status and update CRM Deal
                    si_status = frappe.db.get_value("Sales Invoice", inv_name, "status")
                    if si_status in ["Partially Paid", "Paid"]:
                        frappe.db.set_value(
                            "CRM Deal", doc.crm_deal, "custom_payment_status", si_status
                        )

                except Exception:
                    frappe.log_error(
                        title=f"Payment Entry Creation Failed for {inv_name}",
                        message=frappe.get_traceback(),
                    )

    except Exception:
        frappe.log_error(
            title=f"Subscription Creation Failed: {doc.name}",
            message=frappe.get_traceback(),
        )


@frappe.whitelist()
def broadcast_customer(doc, method=None):
    if doc.get("custom_project_company"):
        return
    broadcast_crm_document(doc, method)


# SECTION 8: SUBSCRIPTION BROADCAST
@frappe.whitelist()
def broadcast_subscription_plan(doc, method=None):
    sub_type = (
        doc.get("custom_subscription_type")
        or doc.get("subscription_type")
        or doc.get("custom_plan_type")
        or doc.get("plan_type")
    )
    if sub_type and str(sub_type).strip().lower() == "addons":
        return

    broadcast_crm_document(doc, method)


@frappe.whitelist()
def broadcast_subscription_wrapper(doc, method=None):
    if not doc:
        return

    broadcast_key = f"integration_broadcasted_{doc.name}"
    if getattr(frappe.flags, broadcast_key, False):
        return
    setattr(frappe.flags, broadcast_key, True)

    # Project resolution is now handled inside broadcast_crm_document
    broadcast_crm_document(doc, method)


@frappe.whitelist()
def send_subscription_status_data(doc, method=None):
    if doc.status != "Active":
        return

    project = frappe.db.get_value("Customer", doc.party, "custom_project") or ""
    if not project:
        return

    target_url, headers = get_project_settings(project, throw=False)
    if not target_url:
        return

    package = doc.plans[0].plan if doc.plans else ""

    billing_cycle = "Monthly"
    if package:
        interval = frappe.db.get_value("Subscription Plan", package, "billing_interval")
        if interval == "Year":
            billing_cycle = "Annual"
        elif interval == "Quarter":
            billing_cycle = "Quarterly"

    payload = {
        "doctype": "Subscription",
        "company_name": doc.party,
        "package": package,
        "billing_cycle": billing_cycle,
        "start_date": doc.start_date,
        "end_date": doc.end_date,
        "status": doc.status,
        "amount_paid": 0,
        "project": project,
    }
    return send_api_request(target_url, headers, payload)


# SECTION 9: INCOMING INTEGRATION
@frappe.whitelist()
def xpert_integration(payload=None):
    if not payload:
        frappe.throw("Payload is required.")

    if isinstance(payload, str):
        payload = frappe.parse_json(payload)

    doctype = payload.get("doctype")
    get_integration_logger().info(f"Incoming request for doctype: {doctype}")

    return process_incoming_integration_payload(payload)


@frappe.whitelist()
def process_incoming_integration_payload(payload=None):
    if not payload:
        frappe.throw("Payload is required.")

    if isinstance(payload, str):
        payload = frappe.parse_json(payload)

    target_doctype = payload.get("doctype")
    if not target_doctype:
        frappe.throw("Payload must contain 'doctype'.")

    logger = get_integration_logger()
    doc_fields = dict(payload)

    # Handle base64 file fields
    for field, value in list(doc_fields.items()):
        if (
            isinstance(value, dict)
            and value.get("file_name")
            and value.get("file_data")
        ):
            try:
                file_name = value["file_name"]
                file_data = base64.b64decode(value["file_data"])

                file_doc = frappe.get_doc(
                    {
                        "doctype": "File",
                        "file_name": file_name,
                        "content": file_data,
                        "is_private": 0,
                    }
                )
                file_doc.insert(ignore_permissions=True)
                doc_fields[field] = file_doc.file_url
            except Exception:
                logger.warning(f"File save failed for field {field}", exc_info=True)
                doc_fields.pop(field, None)
        elif isinstance(value, list):
            _clean_child_table_rows(value)

    # Resolve link fields (Project / Subscription Plan)
    meta = frappe.get_meta(target_doctype)

    for prj_field in ["project", "custom_project"]:
        if meta.has_field(prj_field) and doc_fields.get(prj_field):
            prj_val = doc_fields[prj_field]
            real_name = frappe.db.get_value(
                "Project", {"project_name": prj_val}, "name"
            ) or frappe.db.get_value("Project", prj_val, "name")
            if real_name:
                doc_fields[prj_field] = real_name

    for plan_field in ["plan", "custom_plan"]:
        if meta.has_field(plan_field) and doc_fields.get(plan_field):
            plan_val = doc_fields[plan_field]
            real_name = frappe.db.get_value(
                "Subscription Plan", {"plan_name": plan_val}, "name"
            ) or frappe.db.get_value("Subscription Plan", plan_val, "name")
            if real_name:
                doc_fields[plan_field] = real_name

    try:
        existing = None
        if doc_fields.get("name"):
            existing = frappe.db.exists(target_doctype, doc_fields["name"])

        if existing:
            doc = frappe.get_doc(target_doctype, existing)
            doc.update(doc_fields)
            doc.flags.ignore_integration = True
            doc.save(ignore_permissions=True)
            action = "updated"
        else:
            doc_fields["doctype"] = target_doctype
            doc = frappe.get_doc(doc_fields)
            doc.flags.ignore_integration = True
            doc.insert(ignore_permissions=True)
            action = "created"

        # NOTE: Removed manual frappe.db.commit(). Frappe handles transactions.
        return {
            "status": "success",
            "message": f"{target_doctype} '{doc.name}' {action} successfully.",
            "docname": doc.name,
        }

    except Exception:
        frappe.log_error(
            title="Incoming Integration Failed",
            message=f"Doctype: {target_doctype}\nPayload: {payload}\n\n{frappe.get_traceback()}",
        )
        raise


# SECTION 10: OUTGOING BROADCAST
@frappe.whitelist()
def broadcast_crm_document(doc, method=None):
    if not doc:
        frappe.throw("Document is required.")

    # STRICT BLOCK: Never broadcast a CRM Deal if it is 'Won'
    if getattr(doc, "doctype", "") == "CRM Deal" or (
        isinstance(doc, dict) and doc.get("doctype") == "CRM Deal"
    ):
        status = (
            getattr(doc, "status", None)
            if not isinstance(doc, dict)
            else doc.get("status")
        )
        if status == "Won":
            return

    logger = get_integration_logger()

    # Normalize input to a clean dict WITHOUT mutating the caller's object
    if isinstance(doc, str):
        doc = frappe.parse_json(doc)

    if isinstance(doc, dict):
        # Deep copy via JSON round-trip to ensure isolation
        payload = frappe.parse_json(frappe.as_json(doc))
        doc_name = payload.get("name", "Unknown")
        my_doctype = payload.get("doctype", "Unknown")
        flags = payload.get("flags", {}) or {}
    else:
        doc_name = doc.name
        my_doctype = doc.doctype
        flags = getattr(doc, "flags", {}) or {}
        payload = frappe.parse_json(doc.as_json())

    if flags.get("ignore_integration"):
        logger.info(f"Broadcast skipped (ignore_integration): {my_doctype} {doc_name}")
        return

    if flags.get("integration_broadcasted"):
        return

    # Skip customers that have custom_create_company on their deal
    # if my_doctype == "Customer":
    #     deal_name = payload.get("crm_deal")
    #     if deal_name:
    #         is_create_company = frappe.db.get_value(
    #             "CRM Deal", deal_name, "custom_create_company"
    #         )
    #         if is_create_company:
    #             return

    # Resolve project
    project_val = payload.get("custom_project") or payload.get("project")

    if not project_val and my_doctype == "Subscription":
        party = payload.get("party")
        party_type = payload.get("party_type")
        if party and party_type == "Customer":
            project_val = frappe.db.get_value("Customer", party, "custom_project")
            if project_val:
                payload["custom_project"] = project_val

    if not project_val:
        return

    project_id = (
        frappe.db.get_value("Project", {"project_name": project_val}, "name")
        or frappe.db.get_value("Project", project_val, "name")
        or project_val
    )
    if not project_id:
        return

    project_name = (
        frappe.db.get_value("Project", project_id, "project_name") or project_id
    )

    # Build clean payload
    payload = _build_broadcast_payload(payload, project_id, project_name)

    # Mark original document as broadcasted so subsequent saves don't re-trigger
    if not isinstance(doc, dict):
        doc.flags.integration_broadcasted = True

    try:
        frappe.enqueue(
            "xpertintegration.api.integration._execute_broadcast",
            queue="long",
            payload=payload,
            doctype=my_doctype,
            docname=doc_name,
            project_id=project_id,
            source_doctype=my_doctype,
            source_docname=doc_name,
        )
        return {"status": "enqueued", "message": "Broadcast enqueued in the background"}
    except Exception:
        frappe.log_error(
            title=f"Broadcast Enqueue Failed: {my_doctype} {doc_name}",
            message=frappe.get_traceback(),
        )
        return {"status": "failed", "error": "Failed to enqueue broadcast"}


def _build_broadcast_payload(doc_input, project_id, project_name):
    if isinstance(doc_input, dict):
        payload = frappe.parse_json(frappe.as_json(doc_input))
    else:
        payload = frappe.parse_json(doc_input.as_json())

    _clean_payload_timestamps(payload)

    # Clean child tables
    for field, value in list(payload.items()):
        if isinstance(value, list):
            _clean_child_table_rows(value)

    # Normalize project names to human-readable form for remote
    if payload.get("custom_project") == project_id:
        payload["custom_project"] = project_name
    if payload.get("project") == project_id:
        payload["project"] = project_name

    # Configurable: strip local name to force remote creation
    config = get_broadcast_config()
    if config.get("strip_name_for_remote_create"):
        payload.pop("name", None)

    return payload


def _execute_broadcast(
    payload, doctype, docname, project_id, source_doctype, source_docname
):
    logger = get_integration_logger()
    try:
        target_url, headers = get_project_settings(project_id, throw=False)
        if not target_url:
            logger.warning(f"No project settings for {project_id}, aborting broadcast")
            return

        # Encode file attachments
        meta = frappe.get_meta(doctype)
        file_fields = [
            f.fieldname
            for f in meta.fields
            if f.fieldtype in ("Attach", "Attach Image")
        ]

        for field in file_fields:
            file_url = payload.get(field)
            if not isinstance(file_url, str):
                continue
            if not file_url.startswith(("/files/", "/private/files/")):
                continue

            try:
                file_doc_name = frappe.db.get_value(
                    "File", {"file_url": file_url}, "name"
                )
                if not file_doc_name:
                    continue

                file_doc = frappe.get_doc("File", file_doc_name)
                content = file_doc.get_content()
                if not content:
                    continue

                fname = file_doc.file_name
                ftype, _ = mimetypes.guess_type(fname)
                ext = os.path.splitext(fname)[1].lower() if fname else ""

                payload[field] = {
                    "file_name": fname,
                    "file_type": ftype or "application/octet-stream",
                    "file_extension": ext,
                    "file_data": base64.b64encode(content).decode("utf-8"),
                }
            except Exception:
                logger.warning(
                    f"File encoding failed for {field} in {doctype} {docname}",
                    exc_info=True,
                )

        send_api_request(target_url, headers, payload, source_doctype, source_docname)

    except Exception:
        frappe.log_error(
            title=f"Broadcast Execution Failed: {doctype} {docname}",
            message=frappe.get_traceback(),
        )


@frappe.whitelist()
def broadcast_delete_crm_document(doc, method=None):
    if not doc:
        return

    logger = get_integration_logger()

    # Normalize input
    if isinstance(doc, str):
        doc = frappe.parse_json(doc)

    doc_name = doc.get("name") if isinstance(doc, dict) else doc.name
    my_doctype = doc.get("doctype") if isinstance(doc, dict) else doc.doctype

    project_val = (
        doc.get("custom_project")
        if isinstance(doc, dict)
        else getattr(doc, "custom_project", None)
    )
    if not project_val and my_doctype == "Subscription":
        party = (
            doc.get("party") if isinstance(doc, dict) else getattr(doc, "party", None)
        )
        if party:
            project_val = frappe.db.get_value("Customer", party, "custom_project")

    if not project_val:
        return

    project_id = (
        frappe.db.get_value("Project", {"project_name": project_val}, "name")
        or frappe.db.get_value("Project", project_val, "name")
        or project_val
    )
    if not project_id:
        return

    project_name = (
        frappe.db.get_value("Project", project_id, "project_name") or project_id
    )

    # Build clean payload
    payload = _build_broadcast_payload(doc, project_id, project_name)
    payload["integration_action"] = "delete"

    # Send synchronously so we can block the local deletion if it fails remotely
    target_url, headers = get_project_settings(project_id, throw=False)
    if not target_url:
        logger.warning(
            f"No project settings for {project_id}, aborting delete broadcast"
        )
        return

    try:
        response = send_api_request(target_url, headers, payload, my_doctype, doc_name)
        if response.get("status") == "failed":
            error_data = {}
            error_str = response.get("error", "{}")
            if "{" in error_str:
                try:
                    error_data = json.loads(error_str)
                except Exception:
                    pass

            exc = error_data.get("exc", "")
            # Try to identify LinkExistsError
            if (
                "LinkExistsError" in exc
                or error_data.get("exc_type") == "LinkExistsError"
            ):
                frappe.throw(
                    f"Cannot delete '{doc_name}' because it is in use in the POS system.",
                    exc=frappe.LinkExistsError,
                )

            server_messages = error_data.get("_server_messages")
            if server_messages:
                import ast

                try:
                    messages = ast.literal_eval(server_messages)
                    if messages and isinstance(messages, list):
                        msg_dict = json.loads(messages[0])
                        frappe.throw(f"Remote POS Error: {msg_dict.get('message')}")
                except Exception:
                    frappe.throw(f"Remote POS Error: {server_messages}")

            frappe.throw(f"Failed to delete in remote POS system. Error: {error_str}")

    except Exception as e:
        if isinstance(e, frappe.exceptions.ValidationError):
            raise
        frappe.log_error(
            title=f"Delete Broadcast Failed: {my_doctype} {doc_name}",
            message=frappe.get_traceback(),
        )
        frappe.throw(f"Failed to synchronize deletion with POS system: {str(e)}")


# SECTION 11: CUSTOM SUBSCRIPTION
class CustomSubscription(Subscription):
    def get_items_from_plans(self, plans, prorate=0):
        if not plans:
            return []

        prorate_factor = 1
        if prorate:
            prorate_factor = get_prorata_factor(
                self.current_invoice_end,
                self.current_invoice_start,
                cint(
                    self.generate_invoice_at
                    in [
                        "Beginning of the current subscription period",
                        "Days before the current subscription period",
                    ]
                ),
            )

        # O(1) custom rate lookup (was O(n²) in original)
        custom_rate_map = {}
        if hasattr(self, "plans") and self.plans:
            custom_rate_map = {
                i.plan: i.custom_cost for i in self.plans if hasattr(i, "custom_cost")
            }

        deferred_field = (
            "enable_deferred_revenue"
            if self.party_type == "Customer"
            else "enable_deferred_expense"
        )
        accounting_dimensions = get_accounting_dimensions()

        # Batch-fetch deferred flags for all items
        plan_names = [p.plan for p in plans]
        plan_items = frappe.get_all(
            "Subscription Plan",
            filters={"name": ["in", plan_names]},
            fields=["name", "item"],
        )
        item_codes = list({p.item for p in plan_items if p.item})

        deferred_map = {}
        if item_codes:
            rows = frappe.get_all(
                "Item",
                filters={"name": ["in", item_codes]},
                fields=["name", deferred_field],
            )
            deferred_map = {r.name: r.get(deferred_field) for r in rows}

        items = []
        for plan in plans:
            plan_doc = frappe.get_cached_doc("Subscription Plan", plan.plan)
            item_code = plan_doc.item

            rate_ = get_plan_rate(
                plan.plan,
                plan.qty,
                self.party,
                self.current_invoice_start,
                self.current_invoice_end,
                prorate_factor,
            )
            rate_ = custom_rate_map.get(plan.plan, rate_)

            item = {
                "item_code": item_code,
                "qty": plan.qty,
                "rate": rate_,
                "cost_center": plan_doc.cost_center,
            }

            deferred = deferred_map.get(item_code)
            if deferred:
                item.update(
                    {
                        deferred_field: deferred,
                        "service_start_date": self.current_invoice_start,
                        "service_end_date": self.current_invoice_end,
                    }
                )

            for dimension in accounting_dimensions:
                if plan_doc.get(dimension):
                    item[dimension] = plan_doc.get(dimension)

            items.append(item)

        return items


@frappe.whitelist()
def handle_deal_payment_task(doc, method=None):
    if doc.get("custom_payment_status") == "Verify Payment" and doc.get(
        "custom_payment_proof"
    ):
        company_name = doc.get("organization") or doc.name
        task_title = f"Verify Payment - {company_name}"

        existing = frappe.db.exists(
            "CRM Task",
            {
                "reference_doctype": "CRM Deal",
                "reference_docname": doc.name,
                "title": task_title,
            },
        )
        if not existing:
            try:
                task = frappe.get_doc(
                    {
                        "doctype": "CRM Task",
                        "title": task_title,
                        "assigned_to": "accountant@raabtax.com",
                        "status": "Todo",
                        "reference_doctype": "CRM Deal",
                        "reference_docname": doc.name,
                        "description": f"Verify payment for Deal {doc.name}.<br><br><a href='/app/payment-verification'>Payment Verification Page</a>",
                    }
                )
                task.insert(ignore_permissions=True)
            except Exception:
                frappe.log_error(
                    title=f"Payment Task Creation Failed: {doc.name}",
                    message=frappe.get_traceback(),
                )

    elif doc.get("custom_payment_status") == "Paid":
        company_name = doc.get("organization") or doc.name
        task_title = f"Verify Payment - {company_name}"

        tasks = frappe.get_all(
            "CRM Task",
            filters={
                "reference_doctype": "CRM Deal",
                "reference_docname": doc.name,
                "title": task_title,
                "status": ["!=", "Completed"],
            },
        )
        for t in tasks:
            frappe.db.set_value("CRM Task", t.name, "status", "Completed")


@frappe.whitelist()
def update_deal_payment_status(doc, method=None):
    if doc.get("custom_crm_deal"):
        frappe.db.set_value(
            "CRM Deal", doc.custom_crm_deal, "custom_payment_status", doc.status
        )
