import json
import re
import base64
import mimetypes
import os
import requests

import frappe
from frappe import _
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


def create_integration_log(
    status="Success",
    direction="Outbound",
    trigger_source="DocType Hook",
    reference_doctype=None,
    reference_name=None,
    company_code=None,
    http_method="POST",
    endpoint_url=None,
    response_code=None,
    request_headers=None,
    request_payload=None,
    response_payload=None,
    error_traceback=None,
    remarks=None,
    execution_time=None,
):
    """
    Creates an Integration Log entry to track all sync steps, payloads, responses, and errors.
    """
    try:

        def _serialize(data):
            if data is None:
                return None
            if isinstance(data, (dict, list)):
                try:
                    return json.dumps(data, indent=2, default=str)
                except Exception:
                    return str(data)
            return str(data)

        user = "Administrator"
        try:
            if frappe.session and getattr(frappe.session, "user", None):
                user = frappe.session.user
        except Exception:
            pass

        log_doc = frappe.get_doc(
            {
                "doctype": "Integration Log",
                "status": status,
                "direction": direction,
                "trigger_source": trigger_source,
                "execution_time": flt(execution_time) if execution_time else None,
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "company_code": company_code,
                "http_method": http_method,
                "endpoint_url": endpoint_url,
                "response_code": response_code,
                "triggered_by": user,
                "request_headers": _serialize(request_headers),
                "request_payload": _serialize(request_payload),
                "response_payload": _serialize(response_payload),
                "error_traceback": error_traceback,
                "remarks": remarks,
            }
        )
        log_doc.flags.ignore_permissions = True
        log_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return log_doc.name
    except Exception as e:
        get_integration_logger().error(f"Failed to create Integration Log: {str(e)}")
        return None


def log_integration_error(
    title, message=None, reference_doctype=None, reference_name=None, company_code=None
):
    """
    Logs errors into Integration Log instead of frappe.error_log.
    """
    trace = message if message else frappe.get_traceback()
    try:
        create_integration_log(
            status="Failed",
            direction="Outbound",
            trigger_source="DocType Hook",
            reference_doctype=reference_doctype,
            reference_name=reference_name,
            company_code=company_code,
            error_traceback=trace,
            remarks=title,
        )
    except Exception as e:
        get_integration_logger().error(f"{title}: {trace} (Meta error: {str(e)})")


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
        doc = frappe.get_doc(doctype, name)
        if doc and hasattr(doc, "reload"):
            try:
                doc.reload()
            except Exception:
                pass
        return doc
    except frappe.DoesNotExistError:
        if log_title:
            get_integration_logger().warning(f"{log_title}: {doctype} {name} not found")
        return None
    except Exception:
        if log_title:
            log_integration_error(title=log_title, message=frappe.get_traceback())
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
    import time

    start_time = time.time()
    res_code = None
    resp_payload = None
    status = "Success"
    err_trace = None
    remarks = None

    try:
        response = requests.post(
            target_url,
            headers=headers,
            json={"payload": payload},
            timeout=60,
        )
        res_code = response.status_code
        response.raise_for_status()

        try:
            resp_json = response.json()
            resp_payload = resp_json

            has_remote_error = False
            remote_error_msg = None

            if isinstance(resp_json, dict):
                if resp_json.get("status") in ["failed", "error"]:
                    has_remote_error = True
                    remote_error_msg = (
                        resp_json.get("error")
                        or resp_json.get("message")
                        or "Remote API returned failed status"
                    )
                elif resp_json.get("exc") or resp_json.get("exception"):
                    has_remote_error = True
                    remote_error_msg = resp_json.get("exc") or resp_json.get(
                        "exception"
                    )
                elif isinstance(resp_json.get("message"), dict) and resp_json.get(
                    "message", {}
                ).get("status") in ["failed", "error"]:
                    has_remote_error = True
                    remote_error_msg = resp_json.get("message", {}).get(
                        "error"
                    ) or resp_json.get("message", {}).get("message")

            if has_remote_error:
                status = "Failed"
                err_trace = str(remote_error_msg)
                remarks = f"Remote API Error: {str(remote_error_msg)[:140]}"
                ret_val = {
                    "status": "failed",
                    "error": remote_error_msg,
                    "data": resp_json,
                }
            else:
                if source_doctype and source_docname and isinstance(resp_json, dict):
                    callback_data = resp_json.get("message", {}).get("callback_data")
                    if isinstance(callback_data, dict):
                        frappe.db.set_value(
                            source_doctype, source_docname, callback_data
                        )
                ret_val = {"status": "success", "data": resp_json}
        except ValueError:
            resp_payload = response.text
            ret_val = {"status": "success", "text": response.text}

    except requests.exceptions.HTTPError:
        status = "Failed"
        res_code = getattr(response, "status_code", 500)
        resp_payload = getattr(response, "text", "")
        err_msg = (
            f"HTTP Error {res_code} from {target_url}\n"
            f"Response: {resp_payload}\n"
            f"Payload: {json.dumps(payload, default=str)}"
        )
        logger.error(err_msg)
        err_trace = frappe.get_traceback()
        remarks = f"HTTP Error {res_code}"
        ret_val = {
            "status": "failed",
            "error": resp_payload,
            "status_code": res_code,
        }
    except requests.exceptions.RequestException as e:
        status = "Failed"
        err_msg = (
            f"Network Exception connecting to {target_url}\n"
            f"Error: {str(e)}\n"
            f"Payload: {json.dumps(payload, default=str)}"
        )
        logger.error(err_msg)
        err_trace = frappe.get_traceback()
        remarks = f"Network Exception: {str(e)}"
        ret_val = {"status": "failed", "error": str(e)}

    exec_time = round(time.time() - start_time, 3)

    create_integration_log(
        status=status,
        direction="Outbound",
        trigger_source="DocType Hook",
        reference_doctype=source_doctype
        or (payload.get("doctype") if isinstance(payload, dict) else None),
        reference_name=source_docname
        or (payload.get("name") if isinstance(payload, dict) else None),
        company_code=(
            payload.get("custom_company_code") if isinstance(payload, dict) else None
        ),
        http_method="POST",
        endpoint_url=target_url,
        response_code=res_code,
        request_headers=headers,
        request_payload=payload,
        response_payload=resp_payload,
        error_traceback=err_trace,
        remarks=remarks or f"API Broadcast {status}",
        execution_time=exec_time,
    )

    return ret_val


# SECTION 4: VALIDATION ENGINE
def _normalize_project_id(project_val):
    if not project_val:
        return ""
    proj_id = (
        frappe.db.get_value("Project", {"project_name": project_val}, "name")
        or frappe.db.get_value("Project", project_val, "name")
        or project_val
    )
    return str(proj_id).strip()


def get_doc_project(doc):
    """
    Returns the project associated with the given document, checking doc fields
    and linked parent entities (Lead, Customer, User, etc.) as fallbacks.
    """
    project = (
        doc.get("custom_project") or doc.get("project") or doc.get("custom_project")
    )
    if project:
        return project

    if doc.doctype == "CRM Deal":
        if doc.get("lead"):
            project = frappe.db.get_value("CRM Lead", doc.lead, "custom_project")
        if not project and doc.get("customer"):
            project = frappe.db.get_value("Customer", doc.customer, "custom_project")
    elif doc.doctype == "Subscription":
        if doc.get("party_type") == "Customer" and doc.get("party"):
            project = frappe.db.get_value("Customer", doc.party, "custom_project")
    elif doc.doctype == "Sales Invoice":
        if doc.get("customer"):
            project = frappe.db.get_value("Customer", doc.customer, "custom_project")
        if not project and doc.get("custom_crm_deal"):
            project = frappe.db.get_value(
                "CRM Deal", doc.custom_crm_deal, "custom_project"
            )

    return project


@frappe.whitelist()
def validate_plan_project_matching(doc, method=None):
    """
    Validates that:
    1. Main subscription plan (custom_plan or Subscription plans table) belongs to the SAME project
       as the document (CRM Deal, CRM Lead, Customer, Subscription, Sales Invoice).
    2. Main subscription plan is of type 'Plan' (not 'Addons').
    3. Add-on items in custom_addons_table belong to the SAME project and are of type 'Addons'.
    """
    doc_project = get_doc_project(doc)
    norm_doc_project = _normalize_project_id(doc_project)

    # Validate main plan in `custom_plan` field
    main_plan = doc.get("custom_plan")
    if main_plan:
        plan_meta = frappe.db.get_value(
            "Subscription Plan",
            main_plan,
            ["custom_project", "custom_subscription_type", "plan_name"],
            as_dict=True,
        )
        if plan_meta:
            plan_project = plan_meta.get("custom_project")
            norm_plan_project = _normalize_project_id(plan_project)
            sub_type = plan_meta.get("custom_subscription_type")

            if sub_type == "Addons":
                frappe.throw(
                    f"Selected Subscription Plan '{main_plan}' is an Addon. Only subscription plans (Type 'Plan') can be selected as the main plan."
                )

            if (
                norm_doc_project
                and norm_plan_project
                and norm_doc_project != norm_plan_project
            ):
                frappe.throw(
                    f"The selected Subscription Plan '{main_plan}' belongs to project '{plan_project}', "
                    f"which does not match the project '{doc_project}' of this {doc.doctype}."
                )
            elif not norm_doc_project and norm_plan_project:
                frappe.throw(
                    f"Please select or assign Project '{plan_project}' to this {doc.doctype} before choosing Subscription Plan '{main_plan}'."
                )

    # Validate plans in Subscription doctype `plans` child table
    if doc.doctype == "Subscription" and doc.get("plans"):
        main_plan_count = 0
        for plan_row in doc.plans:
            if not plan_row.plan:
                continue
            plan_meta = frappe.db.get_value(
                "Subscription Plan",
                plan_row.plan,
                ["custom_project", "custom_subscription_type", "plan_name"],
                as_dict=True,
            )
            if plan_meta:
                plan_project = plan_meta.get("custom_project")
                norm_plan_project = _normalize_project_id(plan_project)
                sub_type = plan_meta.get("custom_subscription_type")

                if sub_type != "Addons":
                    main_plan_count += 1

                if (
                    norm_doc_project
                    and norm_plan_project
                    and norm_doc_project != norm_plan_project
                ):
                    frappe.throw(
                        f"Subscription Plan '{plan_row.plan}' (row #{plan_row.idx}) belongs to project '{plan_project}', "
                        f"which does not match the project '{doc_project}' of this Subscription."
                    )
                elif not norm_doc_project and norm_plan_project:
                    frappe.throw(
                        f"Please assign Project '{plan_project}' to this Subscription before choosing Subscription Plan '{plan_row.plan}'."
                    )

        if main_plan_count > 1:
            frappe.throw(
                f"Only one main plan (Type 'Plan') can be added to a Subscription. Found {main_plan_count} main plans in the plans table."
            )

    # Validate add-ons in `custom_addons_table` (CRM Deal / CRM Lead)
    if doc.get("custom_addons_table"):
        for addon_row in doc.custom_addons_table:
            addon_name = addon_row.get("add_on")
            if not addon_name:
                continue
            addon_meta = frappe.db.get_value(
                "Subscription Plan",
                addon_name,
                ["custom_project", "custom_subscription_type", "plan_name"],
                as_dict=True,
            )
            if addon_meta:
                addon_project = addon_meta.get("custom_project")
                norm_addon_project = _normalize_project_id(addon_project)
                sub_type = addon_meta.get("custom_subscription_type")

                if sub_type and sub_type != "Addons":
                    frappe.throw(
                        f"Add-on '{addon_name}' (row #{addon_row.idx}) is of type '{sub_type}'. "
                        f"Only 'Addons' type plans can be added to the Add-ons table."
                    )

                if (
                    norm_doc_project
                    and norm_addon_project
                    and norm_doc_project != norm_addon_project
                ):
                    frappe.throw(
                        f"Add-on '{addon_name}' (row #{addon_row.idx}) belongs to project '{addon_project}', "
                        f"which does not match the project '{doc_project}' of this {doc.doctype}."
                    )
                elif not norm_doc_project and norm_addon_project:
                    frappe.throw(
                        f"Please assign Project '{addon_project}' to this {doc.doctype} before choosing Add-on '{addon_name}'."
                    )


@frappe.whitelist()
def validate_deal_minimum_cost(doc, method=None):
    """
    Validates that custom_sale_price of CRM Deal is not less than
    the custom_minimum_cost of the linked Subscription Plan (custom_plan).
    """
    plan = doc.get("custom_plan")
    if not plan:
        return

    minimum_cost = frappe.db.get_value("Subscription Plan", plan, "custom_minimum_cost")
    if minimum_cost is not None and minimum_cost != "":
        minimum_cost_val = flt(minimum_cost)
        sale_price_val = flt(doc.get("custom_sale_price"))
        if sale_price_val < minimum_cost_val:
            frappe.throw(f"Sale price cannot be less than {minimum_cost_val}")


def sync_deal_email_to_primary_contact(doc):
    """
    If email is added/updated on a CRM Deal:
    1. Finds the primary Contact linked to the deal (from doc.contacts or doc.contact).
    2. Adds doc.email to that Contact's 'email_ids' child table and sets is_primary = 1.
    3. Saves the Contact document and syncs doc.contacts row email so self.email does not get cleared during validate().
    """
    deal_email = (doc.get("email") or "").strip()
    if not deal_email:
        return

    primary_contact_name = None
    primary_crm_contact_row = None

    if doc.get("contacts"):
        for row in doc.contacts:
            if row.get("is_primary"):
                primary_contact_name = row.get("contact")
                primary_crm_contact_row = row
                break
        if not primary_contact_name and len(doc.contacts) > 0:
            primary_contact_name = doc.contacts[0].get("contact")
            primary_crm_contact_row = doc.contacts[0]

    if not primary_contact_name and doc.get("contact"):
        primary_contact_name = doc.contact

    if not primary_contact_name or not frappe.db.exists("Contact", primary_contact_name):
        return

    contact_doc = frappe.get_doc("Contact", primary_contact_name)

    existing_email_row = None
    for em in contact_doc.get("email_ids") or []:
        if (em.email_id or "").strip().lower() == deal_email.lower():
            existing_email_row = em
            break

    contact_modified = False

    if existing_email_row:
        if not existing_email_row.is_primary:
            for em in contact_doc.get("email_ids") or []:
                em.is_primary = 1 if em.name == existing_email_row.name else 0
            contact_modified = True
    else:
        for em in contact_doc.get("email_ids") or []:
            em.is_primary = 0
        contact_doc.append("email_ids", {"email_id": deal_email, "is_primary": 1})
        contact_modified = True

    if contact_modified:
        contact_doc.flags.ignore_permissions = True
        contact_doc.save(ignore_permissions=True)

    if primary_crm_contact_row:
        primary_crm_contact_row.email = deal_email


@frappe.whitelist()
def validate_crm_deal(doc, method=None):
    # Sync email to primary contact so it does not get cleared
    sync_deal_email_to_primary_contact(doc)

    # 0. Validate project and subscription plan matching
    validate_plan_project_matching(doc)

    # Unique company code check for CRM Deal
    company_code = (doc.get("custom_company_code") or "").strip()
    if company_code:
        filters = [["custom_company_code", "=", company_code]]
        if not doc.is_new() and doc.name:
            filters.append(["name", "!=", doc.name])

        existing_deal = frappe.db.exists("CRM Deal", filters)
        if existing_deal:
            frappe.throw(
                _(
                    f"A CRM Deal with Company Code '{company_code}' already exists ({existing_deal})."
                )
            )

    # 1. Auto-calculate amount
    doc.custom_amount = _compute_doc_amount(doc)

    # 2. Minimum cost validation against subscription plan
    validate_deal_minimum_cost(doc)

    # 3. Lock status change & edits on Won deals if Re-run button is NOT active
    if not doc.is_new():
        old_status = frappe.db.get_value("CRM Deal", doc.name, "status")
        if old_status == "Won" and doc.status != "Won":
            frappe.throw(
                "Status of a Deal that is already marked as 'Won' cannot be changed."
            )

        if doc.status == "Won" and not getattr(doc.flags, "ignore_permissions", False):
            billing_status = check_deal_billing_status(doc.name)
            if not billing_status.get("should_show_rerun"):
                old_vals = frappe.db.get_value(
                    "CRM Deal",
                    doc.name,
                    [
                        "custom_sale_price",
                        "custom_paid_amount",
                        "custom_reference_number",
                        "custom_payment_date",
                    ],
                    as_dict=True,
                )
                if old_vals:
                    if (
                        flt(doc.get("custom_sale_price")) != flt(old_vals.get("custom_sale_price"))
                        or flt(doc.get("custom_paid_amount")) != flt(old_vals.get("custom_paid_amount"))
                        or str(doc.get("custom_reference_number") or "") != str(old_vals.get("custom_reference_number") or "")
                        or str(doc.get("custom_payment_date") or "") != str(old_vals.get("custom_payment_date") or "")
                    ):
                        frappe.throw(
                            _(
                                "This Won deal has completed billing and cannot be updated because the Re-run button is not active."
                            )
                        )

    # 4. AI Payment Proof extraction
    # If payment proof is attached AND custom_paid_amount == 0 AND payment date & reference number are not defined
    payment_proof = doc.get("custom_payment_proof")
    paid_amount = flt(doc.get("custom_paid_amount"))
    payment_date = doc.get("custom_payment_date")
    ref_number = doc.get("custom_reference_number") or doc.get("custom_transaction_id")

    print("\n" + "=" * 60)
    print(
        f"[AI_DEBUG] validate_crm_deal called for Deal: {getattr(doc, 'name', 'New Deal')}"
    )
    print(f"[AI_DEBUG] custom_payment_proof: {payment_proof}")
    print(f"[AI_DEBUG] custom_paid_amount: {paid_amount}")
    print(f"[AI_DEBUG] custom_payment_date: {payment_date}")
    print(f"[AI_DEBUG] custom_reference_number: {ref_number}")

    if payment_proof and paid_amount == 0 and not payment_date and not ref_number:
        print(
            "[AI_DEBUG] => Conditions matched! Invoking AI payment proof extraction..."
        )
        try:
            from xpertintegration.api.ai_analytics import payment_proof_analyzer

            result = payment_proof_analyzer.process_deal_doc(doc)
            print(f"[AI_DEBUG] Extraction result: {result}")
        except Exception as e:
            print(f"[AI_DEBUG] Exception during AI payment proof extraction: {e}")
            log_integration_error(
                title=f"AI Payment Extraction Error for Deal {getattr(doc, 'name', 'New')}",
                message=frappe.get_traceback(),
                reference_doctype="CRM Deal",
                reference_name=getattr(doc, "name", None),
            )
    else:
        print(
            f"[AI_DEBUG] => AI extraction skipped. Conditions: payment_proof={bool(payment_proof)}, paid_amount_is_zero={paid_amount == 0}, no_date={not payment_date}, no_ref={not ref_number}"
        )
    print("=" * 60 + "\n")

    # 5. Payment status validation when status is Submitted, Paid, or Verify Payment
    if (
        doc.get("custom_payment_status") in ["Submitted", "Paid"]
        and flt(doc.get("custom_paid_amount")) <= 0
    ):
        frappe.throw(
            "Paid Amount must be greater than 0 when Payment Status is set to Submitted or Paid."
        )

    if doc.get("custom_payment_status") == "Verify Payment":
        if flt(doc.get("custom_paid_amount")) <= 0:
            fallback = flt(doc.get("custom_sale_price")) or flt(doc.get("custom_amount"))
            if fallback > 0:
                doc.custom_paid_amount = fallback

        missing_payment_fields = []
        if flt(doc.get("custom_paid_amount")) <= 0:
            missing_payment_fields.append(
                doc.meta.get_label("custom_paid_amount") or "Paid Amount"
            )
        if not doc.get("custom_payment_date"):
            missing_payment_fields.append(
                doc.meta.get_label("custom_payment_date") or "Payment Date"
            )
        if not (doc.get("custom_reference_number") or doc.get("custom_transaction_id")):
            missing_payment_fields.append(
                doc.meta.get_label("custom_reference_number") or "Reference Number"
            )

        if missing_payment_fields:
            frappe.throw(
                _(
                    "The following fields are mandatory when Payment Status is set to 'Verify Payment': {0}"
                ).format(", ".join(missing_payment_fields))
            )

    # 6. Payment fields when company code exists
    company_code = doc.get("custom_company_code")
    if company_code and not doc.is_new():
        config = get_payment_validation_config()
        missing = [f for f in config["fields"] if not doc.get(f)]
        if missing:
            labels = [doc.meta.get_label(f) for f in missing]
            frappe.throw(config["error_message"].format(fields=", ".join(labels)))

    # 7. Trial & Win conditions
    if doc.status == "Won":
        if doc.is_new():
            frappe.throw(_("A new CRM Deal cannot be set to 'Won'."))

        cust_exists = (
            doc.get("customer")
            or doc.get("erpnext_customer")
            or frappe.db.get_value("CRM Deal", doc.name, "erpnext_customer")
            or frappe.db.get_value("Customer", {"crm_deal": doc.name}, "name")
        )
        if not cust_exists and doc.get("custom_company_code"):
            cust_exists = frappe.db.get_value(
                "Customer",
                {"custom_project_company": doc.get("custom_company_code")},
                "name",
            )

        if not cust_exists:
            # Customer is being created: Payment status MUST be Submitted or Paid
            if doc.get("custom_payment_status") not in ["Submitted", "Paid"]:
                doc.custom_payment_status = "Paid"
        else:
            # Customer already created: If user updates deal, payment status must remain Submitted or Paid
            if doc.get("custom_payment_status") not in ["Submitted", "Paid"]:
                frappe.throw(
                    _("Payment Status must be 'Submitted' or 'Paid' for a Won deal.")
                )

        if flt(doc.get("custom_paid_amount")) <= 0:
            fallback = flt(doc.get("custom_sale_price")) or flt(doc.get("custom_amount"))
            if fallback > 0:
                doc.custom_paid_amount = fallback
            else:
                frappe.throw(_("Paid Amount must be greater than 0 before marking the deal as Won."))
        _validate_deal_trial_or_win_conditions(doc, is_won=True)
    elif doc.status == "In Trial":
        _validate_deal_trial_or_win_conditions(doc, is_won=False)

    # 8. Broadcast as Customer if In Trial
    send_trial_deal_as_customer(doc)


def _validate_deal_trial_or_win_conditions(doc, is_won=False):
    action_text = "winning the deal" if is_won else "changing the status to In Trial"

    project = doc.get("custom_project")
    project_label = doc.meta.get_label("custom_project") or "Project"
    if not project:
        frappe.throw(
            f"Please fill the following mandatory fields before {action_text}: {project_label}"
        )

    # Validate project settings exist and are complete
    target_url, headers = get_project_settings(project, throw=False)
    if not target_url:
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
        frappe.throw(
            f"Please fill the following mandatory fields before {action_text}: {', '.join(labels)}"
        )

    # Company Code & Payment fields check if custom_company_code exists
    company_code = doc.get("custom_company_code")
    if company_code:
        config = get_payment_validation_config()
        missing = [f for f in config["fields"] if not doc.get(f)]
        if missing:
            labels = [doc.meta.get_label(f) for f in missing]
            frappe.throw(config["error_message"].format(fields=", ".join(labels)))


def send_trial_deal_as_customer(doc):
    if doc.status == "In Trial" and not doc.get("custom_company_code"):
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
            log_integration_error(
                title=f"Broadcast Enqueue Failed: {doc.doctype} {doc.name} as Customer",
                message=frappe.get_traceback(),
                reference_doctype=doc.doctype,
                reference_name=doc.name,
            )


@frappe.whitelist()
def validate_crm_fields(doc, method=None):
    # Validate project and subscription plan matching
    validate_plan_project_matching(doc)

    # Unique company code check for CRM Lead
    company_code = (doc.get("custom_company_code") or "").strip()
    if company_code:
        filters = [["custom_company_code", "=", company_code]]
        if not doc.is_new() and doc.name:
            filters.append(["name", "!=", doc.name])

        existing_lead = frappe.db.exists("CRM Lead", filters)
        if existing_lead:
            frappe.throw(
                _(
                    f"A CRM Lead with Company Code '{company_code}' already exists ({existing_lead})."
                )
            )

    # Duplicate company check
    if doc.is_new() and doc.get("organization"):
        existing = frappe.db.exists("Customer", {"customer_name": doc.organization})
        if existing:
            frappe.throw(
                f"A Customer with the company name '{doc.organization}' already exists in the system."
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
def check_mobile_number_exists(mobile_no, lead_id=None):
    if not mobile_no:
        return {"exists": False}

    raw_mobile = str(mobile_no).strip()
    digits_only = re.sub(r"\D", "", raw_mobile)
    if len(digits_only) < 5:
        return {"exists": False}

    conds = [
        "(mobile_no = %s OR REPLACE(REPLACE(REPLACE(REPLACE(mobile_no, ' ', ''), '-', ''), '+', ''), '(', '') LIKE %s)"
    ]
    params = [raw_mobile, f"%{digits_only[-10:]}"]

    if lead_id:
        conds.append("name != %s")
        params.append(lead_id)

    where_clause = " AND ".join(conds)
    query = f"SELECT name, first_name, last_name, organization, lead_name FROM `tabCRM Lead` WHERE {where_clause} LIMIT 1"
    res = frappe.db.sql(query, params, as_dict=True)

    if res:
        existing_lead = res[0]
        lead_title = (
            existing_lead.get("lead_name")
            or f"{existing_lead.get('first_name') or ''} {existing_lead.get('last_name') or ''}".strip()
            or existing_lead.get("organization")
            or existing_lead.get("name")
        )
        return {
            "exists": True,
            "lead_name": existing_lead.name,
            "lead_title": lead_title,
            "message": f"A Lead with this mobile number already exists ({lead_title} - {existing_lead.name}).",
        }

    return {"exists": False}


@frappe.whitelist()
def check_lead_duplicates(email=None, mobile_no=None, lead_id=None):
    results = {
        "email_exists": False,
        "email_message": "",
        "mobile_exists": False,
        "mobile_message": "",
    }

    if email and str(email).strip():
        raw_email = str(email).strip().lower()
        conds = ["LOWER(email) = %s"]
        params = [raw_email]
        if lead_id:
            conds.append("name != %s")
            params.append(lead_id)
        where_clause = " AND ".join(conds)
        query = f"SELECT name, first_name, last_name, organization, lead_name FROM `tabCRM Lead` WHERE {where_clause} LIMIT 1"
        res = frappe.db.sql(query, params, as_dict=True)
        if res:
            existing = res[0]
            title = (
                existing.get("lead_name")
                or f"{existing.get('first_name') or ''} {existing.get('last_name') or ''}".strip()
                or existing.get("organization")
                or existing.get("name")
            )
            results["email_exists"] = True
            results["email_message"] = _(
                "A Lead with this email already exists ({0} - {1})"
            ).format(title, existing.name)

    if mobile_no and str(mobile_no).strip():
        mob_res = check_mobile_number_exists(mobile_no=mobile_no, lead_id=lead_id)
        if mob_res.get("exists"):
            results["mobile_exists"] = True
            results["mobile_message"] = mob_res.get("message")

    return results


@frappe.whitelist()
def validate_customer(doc, method=None):
    validate_plan_project_matching(doc)

    # Unique project company check for Customer
    project_company = (doc.get("custom_project_company") or "").strip()
    if project_company:
        filters = [["custom_project_company", "=", project_company]]
        if not doc.is_new() and doc.name:
            filters.append(["name", "!=", doc.name])

        existing_customer = frappe.db.exists("Customer", filters)
        if existing_customer:
            frappe.throw(
                _(
                    f"A Customer with Project Company '{project_company}' already exists ({existing_customer})."
                )
            )


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

    set_sales_person_from_deal_owner(doc)
    validate_plan_project_matching(doc)


def set_sales_person_from_deal_owner(doc):
    crm_deal = doc.get("custom_crm_deal")
    if not crm_deal and doc.get("customer"):
        crm_deal = frappe.db.get_value("Customer", doc.customer, "crm_deal")
        if crm_deal:
            doc.custom_crm_deal = crm_deal

    if not crm_deal:
        return

    deal_owner = frappe.db.get_value("CRM Deal", crm_deal, "deal_owner")
    if not deal_owner:
        return

    sales_person = frappe.db.get_value(
        "Sales Person", {"custom_user": deal_owner}, "name"
    )
    if not sales_person:
        sales_person = frappe.db.get_value(
            "Sales Person", {"sales_person_name": deal_owner}, "name"
        )
    if not sales_person:
        sales_person = frappe.db.exists("Sales Person", deal_owner)

    if not sales_person:
        return

    existing_persons = [item.sales_person for item in doc.get("sales_team") or []]
    if sales_person not in existing_persons:
        if not doc.get("sales_team"):
            commission_rate = frappe.db.get_value(
                "Sales Person", sales_person, "commission_rate"
            )
            doc.append(
                "sales_team",
                {
                    "sales_person": sales_person,
                    "allocated_percentage": 100.0,
                    "commission_rate": commission_rate,
                },
            )


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
        log_integration_error(
            title=f"Task Creation Failed: {ref_doctype} {ref_name}",
            message=frappe.get_traceback(),
            reference_doctype=ref_doctype,
            reference_name=ref_name,
        )


@frappe.whitelist()
def custom_convert_to_deal(
    lead: str,
    doc=None,
    deal=None,
    existing_contact=None,
    existing_organization=None,
):
    lead_doc = frappe.get_cached_doc("CRM Lead", lead)
    if not lead_doc.email or not str(lead_doc.email).strip():
        frappe.throw(
            _(
                "Email is mandatory to convert Lead to Deal. Please update the Lead with an email address."
            )
        )
    if not lead_doc.mobile_no or not str(lead_doc.mobile_no).strip():
        frappe.throw(
            _(
                "Mobile Number is mandatory to convert Lead to Deal. Please update the Lead with a mobile number."
            )
        )

    from crm.fcrm.doctype.crm_lead.crm_lead import (
        convert_to_deal as original_convert_to_deal,
    )

    return original_convert_to_deal(
        lead=lead,
        doc=doc,
        deal=deal,
        existing_contact=existing_contact,
        existing_organization=existing_organization,
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
        log_integration_error(
            title=f"Lead Conversion Failed: {lead_doc.name}",
            message=frappe.get_traceback(),
            reference_doctype="CRM Lead",
            reference_name=lead_doc.name,
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
        log_integration_error(
            title=f"Deal Task Creation Failed: {doc.name}",
            message=frappe.get_traceback(),
            reference_doctype="CRM Deal",
            reference_name=doc.name,
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


@frappe.whitelist()
def broadcast_deal_company(doc, method=None):
    try:
        if isinstance(doc, str):
            doc = frappe.parse_json(doc)

        company_code = (
            doc.get("custom_company_code")
            if isinstance(doc, dict)
            else getattr(doc, "custom_company_code", None)
        )
        if not company_code:
            return

        doc_name = (
            doc.get("name") if isinstance(doc, dict) else getattr(doc, "name", None)
        )
        is_new = (
            doc.get("__islocal") or not doc_name
            if isinstance(doc, dict)
            else (doc.is_new() if hasattr(doc, "is_new") else not doc_name)
        )

        if not is_new and doc_name:
            db_company_code = frappe.db.get_value(
                "CRM Deal", doc_name, "custom_company_code"
            )
            if db_company_code == company_code:
                return

        payload = frappe.parse_json(doc if isinstance(doc, dict) else doc.as_json())
        payload["doctype"] = "Deal-Company"

        project_val = (
            doc.get("custom_project")
            if isinstance(doc, dict)
            else getattr(doc, "custom_project", None)
        )

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
        payload["doctype"] = "Deal-Company"

        doc_name_label = doc_name or "New Deal"
        target_url, headers = get_project_settings(project_id, throw=False)
        if not target_url:
            return

        source_doctype = doc.get("doctype") if isinstance(doc, dict) else doc.doctype
        response = send_api_request(
            target_url,
            headers,
            payload,
            source_doctype=source_doctype,
            source_docname=doc_name_label,
        )

        if response.get("status") == "success":
            data = response.get("data", {})
            message = data.get("message", {})

            callback_data = {}
            if isinstance(message, dict):
                callback_data = message.get("callback_data", {})

            returned_company = callback_data.get("custom_company_code")
            if not returned_company:
                frappe.throw("Against this project no company found")
        else:
            comp_code = company_code
            proj_code = project_val
            frappe.throw(
                f"Failed to verify company <b>{comp_code}</b> in project <b>{proj_code}</b>"
            )
    except Exception:
        log_integration_error(
            title="Deal-Company Debug: Exception", message=frappe.get_traceback()
        )
        raise


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
        code = deal.get("custom_company_code")
        if code:
            doc.custom_project_company = code


@frappe.whitelist()
def broadcast_customer_company(doc, method=None):
    try:

        if doc.get("custom_project_company"):
            payload = frappe.parse_json(doc.as_json())
            payload["doctype"] = "Customer-Company"

            project_val = doc.get("custom_project")
            if not project_val and doc.get("crm_deal"):
                project_val = frappe.db.get_value(
                    "CRM Deal", doc.crm_deal, "custom_project"
                )

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
            payload["doctype"] = "Customer-Company"

            doc_name = doc.name or "New Customer"
            target_url, headers = get_project_settings(project_id, throw=False)
            if not target_url:

                return

            response = send_api_request(
                target_url,
                headers,
                payload,
                source_doctype=doc.doctype,
                source_docname=doc_name,
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
        log_integration_error(
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
    # end_date = doc.get("custom_activation_end_date")

    start_dt = getdate(start_date or today())
    end_date = (start_dt + relativedelta(years=1)).strftime("%Y-%m-%d")

    try:
        deal_doc = None
        if doc.crm_deal:
            deal_doc = _safe_get_doc("CRM Deal", doc.crm_deal)

        original_price_sum = 0.0
        sale_price_sum = 0.0

        main_plan_orig = (
            flt(deal_doc.get("custom_original_price"))
            if deal_doc and deal_doc.get("custom_original_price")
            else flt(frappe.db.get_value("Subscription Plan", doc.custom_plan, "cost"))
        )
        main_plan_sale = (
            flt(deal_doc.get("custom_sale_price"))
            if deal_doc and deal_doc.get("custom_sale_price") is not None
            else main_plan_orig
        )

        original_price_sum += main_plan_orig
        sale_price_sum += main_plan_sale

        plan_entry = {"plan": doc.custom_plan, "qty": 1, "custom_cost": main_plan_sale}
        plans_list = [plan_entry]

        if deal_doc:
            for addon in deal_doc.get("custom_addons_table", []):
                if addon.add_on:
                    addon_orig = flt(
                        frappe.db.get_value("Subscription Plan", addon.add_on, "cost")
                    )
                    addon_sale = (
                        flt(addon.amount)
                        if addon.get("amount") is not None
                        else addon_orig
                    )

                    original_price_sum += addon_orig
                    sale_price_sum += addon_sale

                    addon_entry = {
                        "plan": addon.add_on,
                        "qty": 1,
                        "custom_cost": addon_sale,
                    }
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
                "generate_invoice_at": "Days before the current subscription period",
                "number_of_days": 5,
                "submit_invoice": 1,
                "status": "Active",
                "custom_cost": original_price_sum,
                "custom_amount_paid": sale_price_sum,
                "custom_project_company": doc.custom_project_company,
                "custom_project": (deal_doc.custom_project if deal_doc else None),
            }
        )
        sub.insert(ignore_permissions=True)
        sub.process()

        create_integration_log(
            status="Success",
            direction="Internal Sync",
            trigger_source="DocType Hook",
            reference_doctype="Subscription",
            reference_name=sub.name,
            company_code=doc.get("custom_project_company"),
            remarks=f"Subscription '{sub.name}' created for Customer '{doc.name}'",
        )

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
                si_doc = frappe.get_doc("Sales Invoice", inv_name)
                set_sales_person_from_deal_owner(si_doc)
                if si_doc.get("sales_team"):
                    si_doc.save(ignore_permissions=True)

                try:
                    from erpnext.accounts.doctype.payment_entry.payment_entry import (
                        get_payment_entry,
                    )

                    pe = get_payment_entry("Sales Invoice", inv_name, bank_account=None)
                    pe.paid_amount = paid_amount
                    pe.received_amount = paid_amount

                    if deal_doc.get("custom_mode_of_payment"):
                        pe.mode_of_payment = deal_doc.custom_mode_of_payment
                    if deal_doc.get("custom_reference_number"):
                        pe.reference_no = deal_doc.custom_reference_number
                    if deal_doc.get("custom_payment_date"):
                        pe.reference_date = deal_doc.custom_payment_date
                    if deal_doc.get("custom_account_paid_to"):
                        pe.paid_to = deal_doc.custom_account_paid_to

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
                    log_integration_error(
                        title=f"Payment Entry Creation Failed for {inv_name}",
                        message=frappe.get_traceback(),
                        reference_doctype="Sales Invoice",
                        reference_name=inv_name,
                    )

    except Exception:
        log_integration_error(
            title=f"Subscription Creation Failed: {doc.name}",
            message=frappe.get_traceback(),
            reference_doctype="Customer",
            reference_name=doc.name,
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
    import time

    start_time = time.time()

    if not payload:
        create_integration_log(
            status="Failed",
            direction="Inbound",
            trigger_source="Webhook / API",
            http_method="POST",
            error_traceback="Payload is required.",
            remarks="Inbound request failed: No payload provided",
        )
        frappe.throw("Payload is required.")

    if isinstance(payload, str):
        payload = frappe.parse_json(payload)

    target_doctype = payload.get("doctype")
    if not target_doctype:
        create_integration_log(
            status="Failed",
            direction="Inbound",
            trigger_source="Webhook / API",
            http_method="POST",
            request_payload=payload,
            error_traceback="Payload must contain 'doctype'.",
            remarks="Inbound request failed: Missing doctype in payload",
        )
        frappe.throw("Payload must contain 'doctype'.")

    logger = get_integration_logger()
    doc_fields = dict(payload)
    company_code = doc_fields.get("custom_company_code") or doc_fields.get(
        "custom_project_company"
    )

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
            try:
                doc.reload()
            except Exception:
                pass
            doc.update(doc_fields)
            doc.flags.ignore_integration = True
            doc.save(ignore_permissions=True)
            try:
                doc.reload()
            except Exception:
                pass
            action = "updated"
        else:
            doc_fields["doctype"] = target_doctype
            doc = frappe.get_doc(doc_fields)
            doc.flags.ignore_integration = True
            doc.insert(ignore_permissions=True)
            try:
                doc.reload()
            except Exception:
                pass
            action = "created"

        exec_time = round(time.time() - start_time, 3)
        res_payload = {
            "status": "success",
            "message": f"{target_doctype} '{doc.name}' {action} successfully.",
            "docname": doc.name,
        }

        create_integration_log(
            status="Success",
            direction="Inbound",
            trigger_source="Webhook / API",
            reference_doctype=target_doctype,
            reference_name=doc.name,
            company_code=company_code,
            http_method="POST",
            request_payload=payload,
            response_payload=res_payload,
            remarks=f"Inbound {target_doctype} {action} successfully",
            execution_time=exec_time,
        )

        return res_payload

    except Exception as e:
        exec_time = round(time.time() - start_time, 3)
        err_trace = frappe.get_traceback()

        create_integration_log(
            status="Failed",
            direction="Inbound",
            trigger_source="Webhook / API",
            reference_doctype=target_doctype,
            reference_name=doc_fields.get("name"),
            company_code=company_code,
            http_method="POST",
            request_payload=payload,
            error_traceback=err_trace,
            remarks=f"Inbound {target_doctype} processing failed: {str(e)}",
            execution_time=exec_time,
        )

        log_integration_error(
            title="Incoming Integration Failed",
            message=f"Doctype: {target_doctype}\nPayload: {payload}\n\n{err_trace}",
            reference_doctype=target_doctype,
            company_code=company_code,
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

    if not project_val and my_doctype == "Sales Invoice":
        customer = payload.get("customer")
        if customer:
            project_val = frappe.db.get_value("Customer", customer, "custom_project")
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
        log_integration_error(
            title=f"Broadcast Enqueue Failed: {my_doctype} {doc_name}",
            message=frappe.get_traceback(),
            reference_doctype=my_doctype,
            reference_name=doc_name,
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
        log_integration_error(
            title=f"Broadcast Execution Failed: {doctype} {docname}",
            message=frappe.get_traceback(),
            reference_doctype=doctype,
            reference_name=docname,
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

    try:
        frappe.enqueue(
            "xpertintegration.api.integration._execute_broadcast_delete",
            queue="long",
            payload=payload,
            doctype=my_doctype,
            docname=doc_name,
            project_id=project_id,
        )
    except Exception:
        log_integration_error(
            title=f"Delete Broadcast Enqueue Failed: {my_doctype} {doc_name}",
            message=frappe.get_traceback(),
            reference_doctype=my_doctype,
            reference_name=doc_name,
        )


def _execute_broadcast_delete(payload, doctype, docname, project_id):
    logger = get_integration_logger()
    try:
        target_url, headers = get_project_settings(project_id, throw=False)
        if not target_url:
            logger.warning(
                f"No project settings for {project_id}, aborting delete broadcast"
            )
            return

        response = send_api_request(target_url, headers, payload, doctype, docname)
        if response.get("status") == "failed":
            error_data = {}
            error_str = response.get("error", "{}")
            if "{" in error_str:
                try:
                    error_data = json.loads(error_str)
                except Exception:
                    pass

            exc = error_data.get("exc", "")
            if (
                "LinkExistsError" in exc
                or error_data.get("exc_type") == "LinkExistsError"
            ):
                error_msg = (
                    f"Cannot delete '{docname}' because it is in use in the POS system."
                )
            else:
                error_msg = f"Failed to delete in remote POS system. Error: {error_str}"

            server_messages = error_data.get("_server_messages")
            if server_messages:
                import ast

                try:
                    messages = ast.literal_eval(server_messages)
                    if messages and isinstance(messages, list):
                        msg_dict = json.loads(messages[0])
                        error_msg = f"Remote POS Error: {msg_dict.get('message')}"
                except Exception:
                    error_msg = f"Remote POS Error: {server_messages}"

            log_integration_error(
                title=f"Remote Delete Failed: {doctype} {docname}",
                message=error_msg,
                reference_doctype=doctype,
                reference_name=docname,
            )

    except Exception:
        log_integration_error(
            title=f"Delete Broadcast Execution Failed: {doctype} {docname}",
            message=frappe.get_traceback(),
            reference_doctype=doctype,
            reference_name=docname,
        )


# SECTION 11: CUSTOM SUBSCRIPTION
@frappe.whitelist()
def validate_subscription(doc, method=None):
    validate_plan_project_matching(doc)

    total_original_cost = 0.0
    total_custom_cost = 0.0

    if hasattr(doc, "plans") and doc.plans:
        for plan_row in doc.plans:
            if not plan_row.plan:
                continue

            plan_orig_cost = flt(
                frappe.db.get_value("Subscription Plan", plan_row.plan, "cost")
            )
            qty = flt(getattr(plan_row, "qty", 1) or 1)
            total_original_cost += plan_orig_cost * qty

            if (
                getattr(plan_row, "custom_cost", None) is None
                or getattr(plan_row, "custom_cost", "") == ""
            ):
                plan_row.custom_cost = plan_orig_cost

            total_custom_cost += flt(plan_row.custom_cost) * qty

    doc.custom_amount_paid = total_custom_cost
    if not getattr(doc, "custom_cost", None):
        doc.custom_cost = total_original_cost


class CustomSubscription(Subscription):
    def validate(self):
        super().validate()
        validate_subscription(self)

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
                log_integration_error(
                    title=f"Payment Task Creation Failed: {doc.name}",
                    message=frappe.get_traceback(),
                    reference_doctype="CRM Deal",
                    reference_name=doc.name,
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


def on_crm_deal_update_billing(doc, method=None):
    if doc.get("status") == "Won":
        process_deal_billing_pipeline(doc)


@frappe.whitelist()
def update_deal_payment_status(doc, method=None):
    if doc.get("custom_crm_deal"):
        frappe.db.set_value(
            "CRM Deal", doc.custom_crm_deal, "custom_payment_status", doc.status
        )


@frappe.whitelist()
def check_user_sales_and_referral(user):
    if not user:
        return {
            "has_sales_person": False,
            "has_referral_code": False,
            "is_crm_lead_profile": False,
        }

    has_sp = bool(frappe.db.exists("Sales Person", {"custom_user": user}))
    has_rc = bool(frappe.db.exists("User Referral Code", {"user": user}))

    is_crm_lead_profile = False
    if frappe.db.exists("User", user):
        user_doc = frappe.get_doc("User", user)
        if user_doc.get("role_profile_name") == "CRM Lead Profile":
            is_crm_lead_profile = True
        elif user_doc.get("role_profiles"):
            for rp in user_doc.role_profiles:
                if (
                    rp.get("role_profile") == "CRM Lead Profile"
                    or rp.get("role_profile_name") == "CRM Lead Profile"
                ):
                    is_crm_lead_profile = True
                    break

    return {
        "has_sales_person": has_sp,
        "has_referral_code": has_rc,
        "is_crm_lead_profile": is_crm_lead_profile,
    }


@frappe.whitelist()
def create_sales_person(user, commission_rate):
    if not user or not frappe.db.exists("User", user):
        frappe.throw(_("User '{0}' does not exist.").format(user))

    existing_sp = frappe.db.get_value("Sales Person", {"custom_user": user}, "name")
    if existing_sp:
        frappe.throw(
            _("Sales Person record '{0}' already exists for this user.").format(
                existing_sp
            )
        )

    user_doc = frappe.get_doc("User", user)
    sp_name = user_doc.full_name or user_doc.first_name or user
    sp_name = sp_name.strip()

    if frappe.db.exists("Sales Person", sp_name):
        sp_name = f"{sp_name} ({user})"

    doc = frappe.get_doc(
        {
            "doctype": "Sales Person",
            "sales_person_name": sp_name,
            "custom_user": user,
            "commission_rate": commission_rate,
            "is_group": 0,
            "enabled": 1,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def create_user_referral_code(user, referral_code):
    if not user or not frappe.db.exists("User", user):
        frappe.throw(_("User '{0}' does not exist.").format(user))

    referral_code = (referral_code or "").strip()
    if not referral_code:
        frappe.throw(_("Referral Code is required."))

    existing_user_code = frappe.db.get_value(
        "User Referral Code", {"user": user}, "name"
    )
    if existing_user_code:
        frappe.throw(
            _("Referral Code '{0}' already exists for this user.").format(
                existing_user_code
            )
        )

    if frappe.db.exists("User Referral Code", {"referral_code": referral_code}):
        frappe.throw(
            _("Referral Code '{0}' is already assigned to another user.").format(
                referral_code
            )
        )

    doc = frappe.get_doc(
        {"doctype": "User Referral Code", "user": user, "referral_code": referral_code}
    )
    doc.insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def process_deal_billing_pipeline(deal_doc):
    """
    Executes and validates the sequential creation of Customer, Subscription,
    Sales Invoice, and Payment Entry for a won CRM Deal.
    Uses explicit if/else conditions to verify each stage, throwing errors with clear explanations if any step fails.
    """
    if isinstance(deal_doc, str):
        deal_doc = frappe.get_doc("CRM Deal", deal_doc)

    if deal_doc.status != "Won":
        return {}

    # STEP 1: CUSTOMER CREATION / VERIFICATION
    cust_name = (
        deal_doc.get("customer")
        or deal_doc.get("erpnext_customer")
        or frappe.db.get_value("CRM Deal", deal_doc.name, "erpnext_customer")
        or frappe.db.get_value("Customer", {"crm_deal": deal_doc.name}, "name")
    )
    if not cust_name and deal_doc.get("custom_company_code"):
        cust_name = frappe.db.get_value(
            "Customer",
            {"custom_project_company": deal_doc.get("custom_company_code")},
            "name",
        )

    if not cust_name:
        # Fallback safeguard to ensure deal_doc has organization or lead_name for Customer creation
        if not deal_doc.organization and not deal_doc.lead_name:
            if deal_doc.lead:
                deal_doc.lead_name = frappe.db.get_value("CRM Lead", deal_doc.lead, "lead_name")
            if not deal_doc.lead_name and deal_doc.email:
                deal_doc.lead_name = deal_doc.email.split("@")[0].capitalize()
            if not deal_doc.lead_name:
                deal_doc.lead_name = deal_doc.name

        try:
            from crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings import (
                create_customer_from_deal,
            )

            settings = frappe.get_single("ERPNext CRM Settings")
            create_customer_from_deal(deal_doc, settings)
        except Exception as e:
            frappe.throw(
                f"Customer creation failed for Deal '{deal_doc.name}': {str(e)}"
            )

        deal_doc.reload()
        cust_name = (
            deal_doc.get("customer")
            or deal_doc.get("erpnext_customer")
            or frappe.db.get_value("CRM Deal", deal_doc.name, "erpnext_customer")
            or frappe.db.get_value("Customer", {"crm_deal": deal_doc.name}, "name")
        )
        if not cust_name and deal_doc.get("custom_company_code"):
            cust_name = frappe.db.get_value(
                "Customer",
                {"custom_project_company": deal_doc.get("custom_company_code")},
                "name",
            )

    if not cust_name or not frappe.db.exists("Customer", cust_name):
        frappe.throw(
            f"Customer creation failed for Deal '{deal_doc.name}'. Customer record was not found after creation."
        )

    cust_doc = frappe.get_doc("Customer", cust_name)

    # Ensure Customer fields are set
    if not cust_doc.get("custom_plan") and deal_doc.get("custom_plan"):
        cust_doc.db_set("custom_plan", deal_doc.custom_plan)
    if not cust_doc.get("crm_deal"):
        cust_doc.db_set("crm_deal", deal_doc.name)

    # STEP 2: SUBSCRIPTION CREATION / VERIFICATION
    sub_name = frappe.db.get_value(
        "Subscription", {"party": cust_name, "status": ["!=", "Cancelled"]}, "name"
    )
    if not sub_name:
        try:
            create_subscription(cust_doc, method=None)
        except Exception as e:
            frappe.throw(
                f"Customer '{cust_name}' was created, but Subscription creation failed for Deal '{deal_doc.name}': {str(e)}"
            )

        sub_name = frappe.db.get_value(
            "Subscription", {"party": cust_name, "status": ["!=", "Cancelled"]}, "name"
        )

    if not sub_name or not frappe.db.exists("Subscription", sub_name):
        frappe.throw(
            f"Customer '{cust_name}' was created successfully, but Subscription creation failed for Deal '{deal_doc.name}'."
        )

    # STEP 3: SALES INVOICE CREATION / VERIFICATION
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"subscription": sub_name, "docstatus": ["!=", 2]},
        fields=["name", "docstatus", "status"],
    )

    if not invoices:
        frappe.throw(
            f"Subscription '{sub_name}' was created successfully, but Sales Invoice generation failed for Customer '{cust_name}'."
        )

    inv_name = invoices[0].name

    # STEP 4: PAYMENT ENTRY CREATION / VERIFICATION
    paid_amount = flt(deal_doc.get("custom_paid_amount"))
    pe_name = None

    if paid_amount > 0:
        pe_refs = frappe.get_all(
            "Payment Entry Reference",
            filters={"reference_doctype": "Sales Invoice", "reference_name": inv_name},
            fields=["parent"],
        )
        if pe_refs:
            for ref in pe_refs:
                pe_status = frappe.db.get_value(
                    "Payment Entry", ref.parent, "docstatus"
                )
                if pe_status != 2:
                    pe_name = ref.parent
                    break

        if not pe_name:
            try:
                from erpnext.accounts.doctype.payment_entry.payment_entry import (
                    get_payment_entry,
                )

                pe = get_payment_entry("Sales Invoice", inv_name, bank_account=None)
                pe.paid_amount = paid_amount
                pe.received_amount = paid_amount

                if deal_doc.get("custom_mode_of_payment"):
                    pe.mode_of_payment = deal_doc.custom_mode_of_payment
                if deal_doc.get("custom_reference_number"):
                    pe.reference_no = deal_doc.custom_reference_number
                if deal_doc.get("custom_payment_date"):
                    pe.reference_date = deal_doc.custom_payment_date
                if deal_doc.get("custom_account_paid_to"):
                    pe.paid_to = deal_doc.custom_account_paid_to

                for ref in pe.references:
                    if ref.reference_name == inv_name:
                        ref.allocated_amount = paid_amount

                pe.insert(ignore_permissions=True)
                pe.submit()
                pe_name = pe.name
            except Exception as e:
                frappe.throw(
                    f"Sales Invoice '{inv_name}' was created successfully, but Payment Entry creation/submission failed for Deal '{deal_doc.name}': {str(e)}"
                )

        if not pe_name or not frappe.db.exists("Payment Entry", pe_name):
            frappe.throw(
                f"Sales Invoice '{inv_name}' was created successfully, but Payment Entry creation failed for Deal '{deal_doc.name}'."
            )

    return {
        "customer": cust_name,
        "subscription": sub_name,
        "sales_invoice": inv_name,
        "payment_entry": pe_name,
    }


@frappe.whitelist()
def rerun_deal_subscription_process(deal_name):
    if not deal_name:
        frappe.throw("Deal Name is required.")

    deal_doc = frappe.get_doc("CRM Deal", deal_name)
    if deal_doc.status != "Won":
        frappe.throw(
            f"Rerun is only permitted for 'Won' deals. Current status: {deal_doc.status}"
        )

    # 1. Identify Customer
    cust_name = deal_doc.get("customer") or frappe.db.get_value(
        "Customer", {"crm_deal": deal_name}, "name"
    )
    if not cust_name and deal_doc.get("custom_company_code"):
        cust_name = frappe.db.get_value(
            "Customer",
            {"custom_project_company": deal_doc.get("custom_company_code")},
            "name",
        )

    if not cust_name:
        frappe.throw(f"No Customer linked to Deal '{deal_name}' found to rerun.")

    # 2. Cancel and Delete existing linked documents (Payment Entry, Sales Invoice, Subscription)
    subscriptions = frappe.get_all(
        "Subscription", filters={"party": cust_name}, fields=["name", "docstatus"]
    )

    for sub_item in subscriptions:
        sub_name = sub_item.name
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={"subscription": sub_name},
            fields=["name", "docstatus"],
        )
        for inv_item in invoices:
            inv_name = inv_item.name
            pe_refs = frappe.get_all(
                "Payment Entry Reference",
                filters={
                    "reference_doctype": "Sales Invoice",
                    "reference_name": inv_name,
                },
                fields=["parent"],
            )
            for ref in pe_refs:
                pe_name = ref.parent
                if frappe.db.exists("Payment Entry", pe_name):
                    pe_doc = frappe.get_doc("Payment Entry", pe_name)
                    if pe_doc.docstatus == 1:
                        pe_doc.flags.ignore_permissions = True
                        pe_doc.cancel()
                    if pe_doc.docstatus in [0, 2]:
                        frappe.delete_doc(
                            "Payment Entry",
                            pe_name,
                            force=True,
                            ignore_permissions=True,
                        )

            if frappe.db.exists("Sales Invoice", inv_name):
                inv_doc = frappe.get_doc("Sales Invoice", inv_name)
                if inv_doc.docstatus == 1:
                    inv_doc.flags.ignore_permissions = True
                    inv_doc.cancel()
                if inv_doc.docstatus in [0, 2]:
                    frappe.delete_doc(
                        "Sales Invoice", inv_name, force=True, ignore_permissions=True
                    )

        if frappe.db.exists("Subscription", sub_name):
            sub_doc = frappe.get_doc("Subscription", sub_name)
            if sub_doc.docstatus == 1:
                sub_doc.flags.ignore_permissions = True
                sub_doc.cancel()
            if sub_doc.docstatus in [0, 2]:
                frappe.delete_doc(
                    "Subscription", sub_name, force=True, ignore_permissions=True
                )

    # 3. Re-run creation pipeline with strict error checking
    result = process_deal_billing_pipeline(deal_doc)

    msg = (
        f"Re-run completed successfully for Deal '<b>{deal_name}</b>'!<br><br>"
        f"• <b>Customer:</b> {result.get('customer')}<br>"
        f"• <b>Subscription:</b> {result.get('subscription')}<br>"
        f"• <b>Sales Invoice:</b> {result.get('sales_invoice')}<br>"
    )
    if result.get("payment_entry"):
        msg += f"• <b>Payment Entry:</b> {result.get('payment_entry')}<br>"

    return msg


@frappe.whitelist()
def update_won_deal_billing_info(
    deal_name,
    custom_sale_price=None,
    custom_paid_amount=None,
    custom_reference_number=None,
    custom_payment_date=None,
):
    """
    Updates billing & payment fields on a Won CRM Deal directly via Python,
    bypassing form-level read-only locks.
    """
    if not deal_name or not frappe.db.exists("CRM Deal", deal_name):
        frappe.throw(_(f"CRM Deal '{deal_name}' does not exist."))

    deal_doc = frappe.get_doc("CRM Deal", deal_name)

    if custom_sale_price is not None:
        deal_doc.custom_sale_price = flt(custom_sale_price)
    if custom_paid_amount is not None:
        deal_doc.custom_paid_amount = flt(custom_paid_amount)
    if custom_reference_number is not None:
        deal_doc.custom_reference_number = str(custom_reference_number)
    if custom_payment_date is not None:
        deal_doc.custom_payment_date = str(custom_payment_date)

    deal_doc.flags.ignore_permissions = True
    deal_doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "Success",
        "message": f"Updated fields on deal '{deal_name}' successfully.",
        "deal_name": deal_name,
    }


@frappe.whitelist()
def check_deal_billing_status(deal_name):
    if not deal_name or not frappe.db.exists("CRM Deal", deal_name):
        return {"should_show_rerun": False}

    deal = frappe.get_doc("CRM Deal", deal_name)
    if deal.status != "Won":
        return {"should_show_rerun": False}

    sale_price = flt(deal.get("custom_sale_price") or deal.get("custom_amount"))
    paid_amount = flt(deal.get("custom_paid_amount"))

    # Show rerun button if sale price does not match paid amount
    if sale_price != paid_amount:
        return {"should_show_rerun": True, "reason": "Price Mismatch"}

    # Show rerun button if Customer is missing
    cust_name = (
        deal.get("customer")
        or deal.get("erpnext_customer")
        or frappe.db.get_value("CRM Deal", deal_name, "erpnext_customer")
        or frappe.db.get_value("Customer", {"crm_deal": deal_name}, "name")
    )
    if not cust_name and deal.get("custom_company_code"):
        cust_name = frappe.db.get_value(
            "Customer",
            {"custom_project_company": deal.get("custom_company_code")},
            "name",
        )

    if not cust_name:
        return {"should_show_rerun": True, "reason": "Missing Customer"}

    # Show rerun button if Subscription is missing
    sub_name = frappe.db.get_value(
        "Subscription", {"party": cust_name, "status": ["!=", "Cancelled"]}, "name"
    )
    if not sub_name:
        return {"should_show_rerun": True, "reason": "Missing Subscription"}

    # Show rerun button if Sales Invoice is missing
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"subscription": sub_name, "docstatus": ["!=", 2]},
        limit=1,
    )
    if not invoices:
        return {"should_show_rerun": True, "reason": "Missing Sales Invoice"}

    inv_name = invoices[0].name

    # Show rerun button if Payment Entry is missing when paid_amount > 0
    if paid_amount > 0:
        pe_refs = frappe.get_all(
            "Payment Entry Reference",
            filters={"reference_doctype": "Sales Invoice", "reference_name": inv_name},
            fields=["parent"],
        )
        has_pe = False
        if pe_refs:
            for ref in pe_refs:
                status = frappe.db.get_value("Payment Entry", ref.parent, "docstatus")
                if status != 2:
                    has_pe = True
                    break
        if not has_pe:
            return {"should_show_rerun": True, "reason": "Missing Payment Entry"}

    return {"should_show_rerun": False}


@frappe.whitelist()
def rerun_incomplete_billing_deals(exclude_deals=None):
    """
    Finds and re-runs billing for all Won CRM Deals with Payment Status 'Paid' that match any of the following incomplete states:
    1. Customer created, but Subscription NOT created.
    2. Customer created & Subscription created, but Sales Invoice NOT created.
    3. Customer created, Subscription created & Sales Invoice created, but Payment Entry NOT created (when paid_amount > 0).

    By default, excludes 'CRM-DEAL-2026-00207'.
    Executes the exact re-run billing process as the CRM Deal form button for matching deals.
    """
    if exclude_deals is None:
        exclude_list = ["CRM-DEAL-2026-00207"]
    elif isinstance(exclude_deals, str):
        ex_str = exclude_deals.strip()
        if ex_str.startswith("[") and ex_str.endswith("]"):
            try:
                exclude_list = json.loads(ex_str)
            except Exception:
                exclude_list = [
                    d.strip() for d in ex_str.strip("[]").split(",") if d.strip()
                ]
        else:
            exclude_list = [d.strip() for d in ex_str.split(",") if d.strip()]
    elif isinstance(exclude_deals, (list, tuple, set)):
        exclude_list = list(exclude_deals)
    else:
        exclude_list = ["CRM-DEAL-2026-00207"]

    if "CRM-DEAL-2026-00207" not in exclude_list and exclude_deals is None:
        exclude_list.append("CRM-DEAL-2026-00207")

    deals = frappe.get_all(
        "CRM Deal",
        filters={"status": "Won", "custom_payment_status": "Paid"},
        fields=[
            "name",
            "custom_company_code",
            "custom_paid_amount",
            "custom_sale_price",
            "custom_amount",
            "custom_payment_status",
        ],
    )

    matching_deals = []

    for deal in deals:
        deal_name = deal.name
        if deal_name in exclude_list:
            continue

        # Identify Customer
        cust_name = frappe.db.get_value(
            "Customer", {"crm_deal": deal_name}, "name"
        )
        if not cust_name and deal.custom_company_code:
            cust_name = frappe.db.get_value(
                "Customer", {"custom_project_company": deal.custom_company_code}, "name"
            )

        # Requirement: Customer MUST be created
        if not cust_name or not frappe.db.exists("Customer", cust_name):
            continue

        sub_name = frappe.db.get_value(
            "Subscription", {"party": cust_name, "status": ["!=", "Cancelled"]}, "name"
        )

        reason = None
        if not sub_name:
            # Condition 1: Customer created, subscription not
            reason = "Customer created, Subscription missing"
        else:
            # Subscription created, check Sales Invoice
            invoices = frappe.get_all(
                "Sales Invoice",
                filters={"subscription": sub_name, "docstatus": ["!=", 2]},
                fields=["name"],
                limit=1,
            )
            if not invoices:
                # Condition 2: Subscriptions created, sales invoice not
                reason = "Subscription created, Sales Invoice missing"
            else:
                inv_name = invoices[0].name
                paid_amount = flt(deal.custom_paid_amount)
                if paid_amount > 0:
                    pe_refs = frappe.get_all(
                        "Payment Entry Reference",
                        filters={
                            "reference_doctype": "Sales Invoice",
                            "reference_name": inv_name,
                        },
                        fields=["parent"],
                    )
                    has_pe = False
                    if pe_refs:
                        for ref in pe_refs:
                            pe_status = frappe.db.get_value(
                                "Payment Entry", ref.parent, "docstatus"
                            )
                            if pe_status != 2:
                                has_pe = True
                                break
                    if not has_pe:
                        # Condition 3: Sales invoice created, not payment entry
                        reason = "Sales Invoice created, Payment Entry missing"

        if reason:
            matching_deals.append(
                {"deal_name": deal_name, "reason": reason, "customer": cust_name}
            )

    results = []
    errors = []

    for item in matching_deals:
        d_name = item["deal_name"]
        try:
            msg = rerun_deal_subscription_process(d_name)
            results.append(
                {
                    "deal_name": d_name,
                    "status": "Success",
                    "reason": item["reason"],
                    "message": msg,
                }
            )
        except Exception as e:
            err_msg = str(e)
            log_integration_error(
                title=f"Bulk Billing Rerun Error for Deal {d_name}",
                message=frappe.get_traceback(),
                reference_doctype="CRM Deal",
                reference_name=d_name,
            )
            errors.append(
                {
                    "deal_name": d_name,
                    "status": "Failed",
                    "reason": item["reason"],
                    "error": err_msg,
                }
            )

    summary = (
        f"Evaluated {len(deals)} Won deals with Payment Status 'Paid'. "
        f"Excluded: {', '.join(exclude_list)}. "
        f"Found {len(matching_deals)} deals matching incomplete billing criteria. "
        f"Successfully re-ran: {len(results)}, Failed: {len(errors)}."
    )

    return {
        "status": "Completed",
        "summary": summary,
        "total_evaluated": len(deals),
        "excluded_deals": exclude_list,
        "matching_deals_count": len(matching_deals),
        "matching_deals": matching_deals,
        "results": results,
        "errors": errors,
    }
