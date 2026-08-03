import frappe
import json
import requests
from frappe.utils import flt


def log_integration_error(title, message):
    """Helper to log errors cleanly in Frappe Error Log."""
    frappe.log_error(
        title=f"XpertIntegration CRM - {title}", message=str(message))


def log_integration_info(title, message):
    """Helper to log informative events."""
    frappe.log_error(
        title=f"XpertIntegration CRM Info - {title}", message=str(message))


@frappe.whitelist()
def xpert_integration(payload=None):
    if not payload:
        frappe.throw("Payload is required.")

    if isinstance(payload, str):
        payload = frappe.parse_json(payload)

    doctype = payload.get("doctype")
    log_integration_info(f"Incoming Request [{doctype}]", json.dumps(
        payload, indent=2, default=str))

    # All incoming requests are dynamically created/updated via Fields Mapper
    return process_incoming_integration_payload(payload)


def create_payment_entry(payload):
    try:
        log_integration_info("create_payment_entry Payload",
                             json.dumps(payload, indent=2, default=str))

        # 1. Project Lookup
        project_input = payload.get("project")
        project_name = None
        if project_input:
            project_name = (
                frappe.db.get_value(
                    "Project", {"project_name": project_input}, "name")
                or frappe.db.get_value("Project", project_input, "name")
            )

        # 2. Party (Customer) Lookup - Optimized SQL Query
        party_input = payload.get("party")
        party_name = None
        if party_input:
            res = frappe.db.sql(
                """
                SELECT name FROM `tabCustomer`
                WHERE customer_name = %s OR custom_project_company = %s OR name = %s
                LIMIT 1
                """,
                (party_input, party_input, party_input),
                as_dict=True
            )
            if res:
                party_name = res[0].name

        if not party_name and party_input:
            log_integration_error("create_payment_entry - Party Missing",
                                  f"Customer '{party_input}' not found in CRM.")
            frappe.throw(f"Customer '{party_input}' not found in CRM.")

        # 3. Company & Default Accounts
        company = (
            payload.get("company")
            or frappe.db.get_single_value("Global Defaults", "default_company")
            or "RaabtaX"
        )
        company_doc = frappe.get_doc("Company", company)
        paid_from = company_doc.default_receivable_account
        paid_to = company_doc.default_cash_account or company_doc.default_bank_account

        fields = {
            "doctype": "Payment Entry",
            "payment_type": payload.get("payment_type") or "Receive",
            "party_type": payload.get("party_type") or "Customer",
            "party": party_name,
            "company": company,
            "paid_from": paid_from,
            "paid_to": paid_to,
            "posting_date": payload.get("posting_date"),
            "paid_amount": flt(payload.get("paid_amount")),
            "received_amount": flt(payload.get("received_amount") or payload.get("paid_amount")),
            "reference_no": payload.get("reference_no") or "",
            "reference_date": payload.get("reference_date") or payload.get("posting_date"),
            "remarks": payload.get("remarks") or "",
        }

        if project_name:
            fields["project"] = project_name

        if payload.get("references"):
            fields["references"] = payload.get("references")

        doc = frappe.get_doc(fields)
        doc.insert(ignore_permissions=True)

        if payload.get("docstatus") == 1:
            doc.submit()

        frappe.db.commit()

        log_integration_info("create_payment_entry - Success",
                             f"Payment Entry created: {doc.name}")

        return {"status": "success", "message": f"Payment Entry {doc.name} created successfully."}

    except Exception as e:
        log_integration_error("create_payment_entry - Exception",
                              f"Error: {str(e)}\nPayload: {str(payload)}")
        raise


def create_crm_customer_from_saas(payload):
    company_name = payload.get("company_name")
    saas_company_name = payload.get("company_code") or company_name
    email = payload.get("email")

    project_input = payload.get("project") or "SaleDesk"
    project = frappe.db.get_value("XpertIntegration Setting Table", {"project": project_input}, "project") \
        or frappe.db.get_value("XpertIntegration Setting Table", {}, "project")

    existing = frappe.db.get_value(
        "Customer", {"customer_name": company_name}, "name")

    if existing:
        doc = frappe.get_doc("Customer", existing)
        doc.db_set("custom_project_company", saas_company_name)
        log_integration_info("create_crm_customer_from_saas Updated",
                             f"Customer {existing} updated with company {saas_company_name}")
        return {"status": "success", "customer_name": doc.name}

    fields = {
        "doctype": "Customer",
        "customer_name": company_name,
        "customer_group": "Commercial",
        "territory": "All Territories",
        "customer_type": "Company",
        "email_id": email,
        "mobile_no": payload.get("mobile"),
        "custom_project_company": saas_company_name,
        "custom_project": project or ""
    }
    try:
        doc = frappe.get_doc(fields)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        log_integration_info("create_crm_customer_from_saas Created",
                             f"Customer {doc.name} created for SaaS Company {saas_company_name}")
        return {"status": "success", "customer_name": doc.name}
    except Exception as e:
        log_integration_error("create_crm_customer_from_saas Exception",
                              f"Failed to create Customer for {company_name}: {e}")
        return {"status": "failed", "message": str(e)}


def create_crm_lead(payload):
    try:
        log_integration_info("create_crm_lead Incoming Payload",
                             json.dumps(payload, indent=2, default=str))

        project_input = payload.get("project")
        project = (
            frappe.db.get_value(
                "Project", {"project_name": project_input}, "name")
            or frappe.db.get_value("Project", project_input, "name")
        )

        if not project:
            log_integration_error("create_crm_lead Validation Failed",
                                  f"Project not found for project: {project_input}")
            frappe.throw("Project is required in the payload.")

        source_input = payload.get("source")
        source = None
        if source_input:
            source = (
                frappe.db.get_value("CRM Lead Source", source_input, "name")
                or frappe.db.get_value("CRM Lead Source", {"source_name": source_input}, "name")
            )

        fields = {
            "doctype": "CRM Lead",
            "first_name": payload.get("lead_name"),
            "email": payload.get("email"),
            "mobile_no": payload.get("mobile"),
            "custom_project": project,
            "organization": payload.get("customer_name") or "",
            "custom_subject": payload.get("subject") or "",
            "custom_remarks": payload.get("remarks") or "",
            "custom_plan": payload.get("plan"),
            "custom_city": payload.get("city"),
            "status": "Open",
        }

        if source:
            fields["source"] = source

        doc = frappe.get_doc(fields)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        log_integration_info("create_crm_lead Success",
                             f"CRM Lead created: {doc.name}")
        return {"status": "success", "message": f"CRM Lead {doc.name} created successfully."}

    except Exception as e:
        log_integration_error("create_crm_lead Exception",
                              f"Error: {str(e)}\nPayload: {str(payload)}")
        raise


def create_issue(payload):
    project = payload.get("project")
    if not project:
        frappe.throw("Project is required in the payload.")

    fields = {
        "doctype": "Issue",
        "subject": payload.get("subject"),
        "project": project,
        "customer": payload.get("customer_name") or "",
        "raised_by": payload.get("email") or "",
        "description": payload.get("remarks") or "",
        "status": "Open",
        "priority": payload.get("priority") or "",
        "issue_type": payload.get("issue_type") or "",
    }

    try:
        doc = frappe.get_doc(fields)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {"status": "success", "message": "Issue created successfully."}
    except Exception as e:
        log_integration_error("create_issue Exception",
                              f"Payload: {payload}\nError: {e}")
        raise


def update_invoice(payload):
    invoice_name = payload.get("crm_invoice")
    if not invoice_name:
        frappe.throw("crm_invoice is required in payload")

    if not frappe.db.exists("Sales Invoice", invoice_name):
        frappe.throw(f"No Sales Invoice found: {invoice_name}")

    try:
        doc = frappe.get_doc("Sales Invoice", invoice_name)
        new_status = payload.get("status")
        if new_status:
            doc.db_set("status", new_status)

        frappe.db.commit()
        return {"name": doc.name, "status": doc.status}
    except Exception as e:
        log_integration_error("update_invoice Exception",
                              f"Invoice: {invoice_name}\nError: {e}")
        raise


def get_project_settings(project, throw=True):
    if not project:
        if throw:
            frappe.throw("Project is required to get integration settings.")
        return None, None

    project_setting = frappe.db.sql(
        """
        SELECT 
            project,
            base_url,
            api_url,
            api_key,
            api_secret
        FROM `tabXpertIntegration Setting Table`
        WHERE project = %s
        LIMIT 1
        """,
        (project,),
        as_dict=True,
    )

    if not project_setting:
        if throw:
            frappe.throw(f"No Project Setting found for project: {project}")
        return None, None

    setting = project_setting[0]
    base_url = (setting.get("base_url") or "").rstrip("/")
    api_key = setting.get("api_key")
    api_secret = setting.get("api_secret")
    api_endpoint = (setting.get("api_url") or "").strip()

    if not base_url or not api_key or not api_secret:
        if throw:
            frappe.throw(
                f"Base URL or API Key/Secret is missing for project '{project}'.")
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

    return target_url, headers


def send_api_request(target_url, headers, payload, source_doctype=None, source_docname=None):
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
                if callback_data and isinstance(callback_data, dict):
                    frappe.db.set_value(source_doctype, source_docname, callback_data)
                    frappe.db.commit()
            return {"status": "success", "data": resp_json}
        except Exception:
            return {"status": "success", "text": response.text}

    except requests.exceptions.HTTPError as e:
        err_msg = f"HTTP Error {response.status_code} from {target_url}\nResponse: {response.text}\nPayload: {json.dumps(payload, default=str)}"
        log_integration_error("API Request HTTP Error", err_msg)
        return {"status": "failed", "error": response.text, "status_code": response.status_code}
    except requests.exceptions.RequestException as e:
        err_msg = f"Network Exception connecting to {target_url}\nError: {str(e)}\nPayload: {json.dumps(payload, default=str)}"
        log_integration_error("API Request Network Error", err_msg)
        return {"status": "failed", "error": str(e)}


@frappe.whitelist()
def validate_crm_deal(doc, method=None):
    if not doc.is_new():
        old_status = frappe.db.get_value("CRM Deal", doc.name, "status")
        if old_status == "Won":
            frappe.throw(
                "This Deal has already been marked as 'Won' and cannot be edited.")

    if doc.status == "Won":
        project = doc.get("custom_project")
        project_label = doc.meta.get_label("custom_project") or "Project"
        if not project:
            frappe.throw(
                f"Please fill the following mandatory fields before winning the deal: {project_label}")

        project_setting = frappe.db.sql(
            """
            SELECT 
                project,
                base_url,
                api_url,
                api_key,
                api_secret
            FROM `tabXpertIntegration Setting Table`
            WHERE project = %s
            LIMIT 1
            """,
            (project,),
            as_dict=True,
        )

        if not project_setting:
            return

        setting = project_setting[0]
        missing_settings = []
        if not setting.get("base_url"):
            missing_settings.append("Base URL")
        if not setting.get("api_url"):
            missing_settings.append("API URL")
        if not setting.get("api_key"):
            missing_settings.append("API Key")
        if not setting.get("api_secret"):
            missing_settings.append("API Secret")

        if missing_settings:
            frappe.throw(
                f"Project settings for '{project}' are incomplete. Missing: {', '.join(missing_settings)}"
            )

        if not doc.email and doc.lead:
            doc.email = frappe.db.get_value("CRM Lead", doc.lead, "email")
        if not doc.mobile_no and doc.lead:
            doc.mobile_no = frappe.db.get_value(
                "CRM Lead", doc.lead, "mobile_no")

        mandatory_fields = [
            "first_name", "email", "mobile_no", "custom_city",
            "custom_sub_domain", "custom_plan", "custom_password",
            "custom_activation_start_date", "custom_activation_end_date"
        ]
        missing_labels = [doc.meta.get_label(
            f) for f in mandatory_fields if not doc.get(f)]
        if missing_labels:
            frappe.throw(
                f"Please fill the following mandatory fields before winning the deal: {', '.join(missing_labels)}"
            )


@frappe.whitelist()
def create_subscription_for_customer(doc, method=None):
    if not doc.crm_deal:
        return

    if not doc.get("custom_plan"):
        return

    sub_exists = frappe.db.exists("Subscription", {"party": doc.name})
    if sub_exists:
        return

    company = frappe.defaults.get_user_default(
        "Company") or frappe.db.get_value("Company")

    start_date = doc.get("custom_activation_start_date")
    end_date = doc.get("custom_activation_end_date")

    if start_date:
        start_date = str(start_date)
    if end_date:
        end_date = str(end_date)

    try:
        plan_doc = frappe.get_doc("Subscription Plan", doc.custom_plan)
        interval = plan_doc.billing_interval
        interval_count = plan_doc.billing_interval_count or 1

        from dateutil.relativedelta import relativedelta

        start_dt = frappe.utils.getdate(start_date or frappe.utils.today())

        if interval == "Year":
            min_end = start_dt + relativedelta(years=interval_count)
        elif interval == "Quarter":
            min_end = start_dt + relativedelta(months=3 * interval_count)
        elif interval == "Month":
            min_end = start_dt + relativedelta(months=interval_count)
        else:
            min_end = start_dt + relativedelta(months=1)

        if end_date:
            actual_end = frappe.utils.getdate(end_date)
            if actual_end < min_end:
                end_date = min_end.strftime("%Y-%m-%d")
        else:
            end_date = min_end.strftime("%Y-%m-%d")

    except Exception:
        if not end_date:
            from dateutil.relativedelta import relativedelta
            start_dt = frappe.utils.getdate(start_date or frappe.utils.today())
            end_date = (start_dt + relativedelta(years=1)).strftime("%Y-%m-%d")

    try:
        sub = frappe.get_doc({
            "doctype": "Subscription",
            "party_type": "Customer",
            "party": doc.name,
            "company": company,
            "plans": [
                {"plan": doc.custom_plan, "qty": 1}
            ],
            "start_date": start_date or frappe.utils.today(),
            "end_date": end_date,
            "generate_invoice_at": "Beginning of the current subscription period",
            "submit_invoice": 1,
        })
        sub.insert(ignore_permissions=True)
        sub.process()
    except Exception as e:
        log_integration_error("create_subscription_for_customer Exception",
                              f"Failed to create Subscription for {doc.name}: {str(e)}")


@frappe.whitelist()
def before_customer_insert(doc, method=None):
    if not doc.crm_deal:
        return

    deal = frappe.get_doc("CRM Deal", doc.crm_deal)

    fields_to_sync = [
        "custom_password",
        "custom_city",
        "custom_plan",
        "custom_sub_domain",
        "custom_sample_data",
        "custom_activation_start_date",
        "custom_activation_end_date",
        "custom_sell_only_products",
        "custom_project"
    ]
    for field in fields_to_sync:
        if not doc.get(field) and deal.get(field) is not None:
            doc.set(field, deal.get(field))

    if not doc.get("first_name") and deal.get("first_name"):
        doc.first_name = deal.first_name
    if not doc.get("last_name") and deal.get("last_name"):
        doc.last_name = deal.last_name
    if not doc.get("email_id") and deal.get("email"):
        doc.email_id = deal.email
    if not doc.get("mobile_no") and deal.get("mobile_no"):
        doc.mobile_no = deal.mobile_no


@frappe.whitelist()
def after_crm_deal_insert(doc, method=None):
    if doc.get("custom_assigned_to"):
        try:
            task = frappe.get_doc({
                "doctype": "CRM Task",
                "title": f"Follow up on Deal: {doc.name}",
                "assigned_to": doc.custom_assigned_to,
                "status": "Todo",
                "reference_doctype": "CRM Deal",
                "reference_docname": doc.name,
                "description": f"Automatically created task for Deal {doc.name}"
            })
            task.insert(ignore_permissions=True)
        except Exception as e:
            log_integration_error("after_crm_deal_insert Exception",
                                  f"Failed to create CRM Task for Deal {doc.name}: {str(e)}")


@frappe.whitelist()
def after_crm_lead_insert(doc, method=None):
    if doc.get("custom_assigned_to"):
        try:
            task = frappe.get_doc({
                "doctype": "CRM Task",
                "title": f"Follow up on Lead: {doc.name}",
                "assigned_to": doc.custom_assigned_to,
                "status": "Todo",
                "reference_doctype": "CRM Lead",
                "reference_docname": doc.name,
                "description": f"Automatically created task for Lead {doc.name}"
            })
            task.insert(ignore_permissions=True)
        except Exception as e:
            log_integration_error("after_crm_lead_insert Exception",
                                  f"Failed to create CRM Task for Lead {doc.name}: {str(e)}")


@frappe.whitelist()
def before_sales_invoice_insert(doc, method=None):
    if doc.get("subscription"):
        if not doc.get("project") and doc.get("customer"):
            project = frappe.db.get_value(
                "Customer", doc.customer, "custom_project")
            if project:
                doc.project = project


@frappe.whitelist()
def send_subscription_status_data(doc, method=None):
    if doc.status == "Active":
        project = frappe.db.get_value(
            "Customer", doc.party, "custom_project") or ""
        if not project:
            return

        target_url, headers = get_project_settings(project)
        if not target_url:
            return

        package = ""
        if doc.plans:
            package = doc.plans[0].plan

        billing_cycle = "Monthly"
        if package:
            try:
                interval = frappe.db.get_value(
                    "Subscription Plan", package, "billing_interval")
                if interval == "Year":
                    billing_cycle = "Annual"
                elif interval == "Quarter":
                    billing_cycle = "Quarterly"
            except Exception:
                pass

        payload = {
            "doctype": "Subscription",
            "company_name": doc.party,
            "package": package,
            "billing_cycle": billing_cycle,
            "start_date": doc.start_date,
            "end_date": doc.end_date,
            "status": doc.status,
            "amount_paid": 0,
            "project": project
        }
        return send_api_request(target_url, headers, payload)


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


def get_call_log_summary(call_type_str, date_str, status):
    icon = STATUS_ICONS.get(status, "")
    status_display = f"{icon} {status}".strip() if status else ""
    if status_display:
        return f"{call_type_str} • {date_str} • {status_display}"
    return f"{call_type_str} • {date_str}"


@frappe.whitelist()
def update_lead_last_call_log(doc, method=None):
    if doc.reference_doctype == "CRM Lead" and doc.reference_docname:
        call_type = "Inbound Call" if doc.type == "Incoming" else "Outbound Call"
        date_str = frappe.utils.format_date(doc.creation, "MMM dd, yyyy")
        status = doc.status or ""

        summary = get_call_log_summary(call_type, date_str, status)
        frappe.db.set_value("CRM Lead", doc.reference_docname,
                            "custom_last_call_log", summary)


@frappe.whitelist()
def sync_all_leads_last_call_log():
    """
    Manual bulk sync function to update custom_last_call_log on all CRM Leads 
    using their latest CRM Call Log.
    """
    call_logs = frappe.get_all(
        "CRM Call Log",
        filters={"reference_doctype": "CRM Lead"},
        fields=["name", "reference_docname", "type", "status", "creation"],
        order_by="creation asc"
    )

    updated_leads = set()
    for log in call_logs:
        if not log.reference_docname:
            continue

        call_type = "Inbound Call" if log.type == "Incoming" else "Outbound Call"
        date_str = frappe.utils.format_date(log.creation, "MMM dd, yyyy")
        status = log.status or ""

        summary = get_call_log_summary(call_type, date_str, status)
        frappe.db.set_value("CRM Lead", log.reference_docname,
                            "custom_last_call_log", summary)
        updated_leads.add(log.reference_docname)


@frappe.whitelist()
def process_incoming_integration_payload(payload=None):
    """
    Direct record processor for CRM (No Fields Mapper on CRM side).
    Receives pre-mapped payload from client/POS systems and inserts or updates the target CRM document.
    """
    if not payload:
        frappe.throw("Payload is required.")

    if isinstance(payload, str):
        payload = frappe.parse_json(payload)

    target_doctype = payload.get("doctype")
    if not target_doctype:
        frappe.throw("Payload must contain 'doctype'.")

    # Create a copy of payload data to use for document creation/update
    doc_fields = dict(payload)

    # Resolve project link field to actual Project record 'name' if project/custom_project is passed
    meta = frappe.get_meta(target_doctype)
    for prj_field in ["project", "custom_project"]:
        if meta.has_field(prj_field) and doc_fields.get(prj_field):
            prj_val = doc_fields.get(prj_field)
            real_project_name = (
                frappe.db.get_value(
                    "Project", {"project_name": prj_val}, "name")
                or frappe.db.get_value("Project", prj_val, "name")
            )
            if real_project_name:
                doc_fields[prj_field] = real_project_name

    # Resolve plan link field to actual Subscription Plan record 'name' if plan/custom_plan is passed
    for plan_field in ["plan", "custom_plan"]:
        if meta.has_field(plan_field) and doc_fields.get(plan_field):
            plan_val = doc_fields.get(plan_field)
            real_plan_name = (
                frappe.db.get_value("Subscription Plan", {
                                    "plan_name": plan_val}, "name")
                or frappe.db.get_value("Subscription Plan", plan_val, "name")
            )
            if real_plan_name:
                doc_fields[plan_field] = real_plan_name

    try:
        existing_doc_name = None
        if "name" in doc_fields and doc_fields.get("name"):
            existing_doc_name = frappe.db.exists(
                target_doctype, doc_fields["name"])

        if existing_doc_name:
            doc = frappe.get_doc(target_doctype, existing_doc_name)
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

        frappe.db.commit()
        return {
            "status": "success",
            "message": f"{target_doctype} '{doc.name}' {action} successfully.",
            "docname": doc.name
        }
    except Exception as e:
        log_integration_error("Process Incoming Integration Payload Failed",
                              f"Doctype: {target_doctype}\nPayload: {payload}\nError: {e}")
        raise


@frappe.whitelist()
def broadcast_crm_document(doc, method=None):
    """
    Dynamic outbound broadcaster for CRM. Converts doc to dict and sends directly to POS/Client endpoint.
    """
    if not doc:
        frappe.throw("Document is required.")

    if getattr(doc, "flags", {}).get("ignore_integration"):
        return

    if isinstance(doc, str):
        doc = frappe.parse_json(doc)

    my_doctype = doc.get("doctype") if isinstance(doc, dict) else doc.doctype
    project_val = doc.get("custom_project") or doc.get("project") if isinstance(
        doc, dict) else getattr(doc, "custom_project", None) or getattr(doc, "project", "SaleDesk")

    # Resolve project to Project name if project_name is passed
    project_id = (
        frappe.db.get_value("Project", {"project_name": project_val}, "name")
        or frappe.db.get_value("Project", project_val, "name")
        or project_val
    )
    if not project_id:
        project_id = "SaleDesk"

    project_name = frappe.db.get_value("Project", project_id, "project_name") or project_id

    # Send full document dictionary from CRM directly (serialize to handle datetimes)
    payload_str = frappe.as_json(doc) if hasattr(doc, "as_json") else json.dumps(dict(doc), default=str)
    payload = frappe.parse_json(payload_str)

    # Replace project ID with project_name in payload for downstream systems
    if "custom_project" in payload and payload["custom_project"] == project_id:
        payload["custom_project"] = project_name
    if "project" in payload and payload["project"] == project_id:
        payload["project"] = project_name

    try:
        target_url, headers = get_project_settings(project_id)
        frappe.enqueue(
            "xpertintegration.api.integration.send_api_request",
            queue="short",
            target_url=target_url,
            headers=headers,
            payload=payload,
            source_doctype=my_doctype,
            source_docname=doc.name,
            now=frappe.flags.in_test
        )
        return {"status": "enqueued", "message": "Broadcast enqueued in the background"}
    except Exception as e:
        doc_name = doc.get("name") if isinstance(
            doc, dict) else getattr(doc, "name", "Unknown")
        log_integration_error("Broadcast CRM Document Failed",
                              f"Doctype: {my_doctype}, Doc: {doc_name}\nError: {e}")
        return {"status": "failed", "error": str(e)}
