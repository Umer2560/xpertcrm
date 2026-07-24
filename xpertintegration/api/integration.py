import frappe
import requests


@frappe.whitelist()
def xpert_integration(payload=None):
    if not payload:
        frappe.throw("Payload is required.")

    if payload.get("doctype") == "CRM Lead":
        return create_crm_lead(payload)

    if payload.get("doctype") == "Sales Invoice":
        return update_invoice(payload)

    if payload.get("doctype") == "SaaS Company":
        return create_crm_customer_from_saas(payload)


def create_crm_customer_from_saas(payload):
    company_name = payload.get("company_name")
    saas_company_name = payload.get("company_code") or company_name
    email = payload.get("email")
    
    project = frappe.db.get_value("XpertIntegration Setting Table", {}, "project")

    existing = frappe.db.get_value("Customer", {"customer_name": company_name}, "name")
    
    if existing:
        doc = frappe.get_doc("Customer", existing)
        doc.db_set("custom_project_company", saas_company_name)
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
        return {"status": "success", "customer_name": doc.name}
    except Exception as e:
        return {"status": "failed", "message": str(e)}


def create_crm_lead(payload):
    project = payload.get("project")
    if not project:
        frappe.throw("Project is required in the payload.")

    fields = {
        "doctype": "CRM Lead",
        "first_name": payload.get("lead_name"),
        "email": payload.get("email"),
        "mobile_no": payload.get("mobile_no"),
        "project": project,
        "organization": payload.get("customer_name") or "",
        "custom_subject": payload.get("subject") or "",
        "custom_remarks": payload.get("remarks") or "",
        "status": "Open",
    }

    doc = frappe.get_doc(fields)
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success", "message": "CRM Lead created successfully."}


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

    doc = frappe.get_doc(fields)
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success", "message": "Issue created successfully."}


def update_invoice(payload):
    invoice_name = payload.get("crm_invoice")
    if not invoice_name:
        frappe.throw("crm_invoice is required in payload")

    if not frappe.db.exists("Sales Invoice", invoice_name):
        frappe.throw(f"No Sales Invoice found: {invoice_name}")

    doc = frappe.get_doc("Sales Invoice", invoice_name)

    new_status = payload.get("status")
    if new_status:
        doc.db_set("status", new_status)

    frappe.db.commit()

    return {"name": doc.name, "status": doc.status}


def get_project_settings(project):
    if not project:
        return

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
        """,
        (project,),
        as_dict=True,
    )

    if not project_setting:
        frappe.throw(f"No Project Setting found for project: {project}")

    base_url = project_setting[0].get("base_url")
    api_key = project_setting[0].get("api_key")

    if not base_url or not api_key:
        frappe.throw(
            "Base URL or API Key is missing from the associated Project record."
        )

    base = base_url.rstrip("/")
    api_endpoint = project_setting[0].get("api_url", "").strip()

    if not api_endpoint:
        frappe.throw("API URL is not configured in the Project.")

    if not api_endpoint.startswith("/"):
        api_endpoint = "/" + api_endpoint

    target_url = f"{base}{api_endpoint}"

    api_secret = project_setting[0].get("api_secret")
    headers = {
        "Authorization": f"token {api_key}:{api_secret}",
        "Content-Type": "application/json",
    }

    return target_url, headers


def send_api_request(target_url, headers, payload):
    try:
        response = requests.post(
            target_url,
            headers=headers,
            json={"payload": payload},
            timeout=30,
        )
        response.raise_for_status()
        # frappe.msgprint(
        #     f"API request successful. Response: {response.text.message}")
        try:
            return {"status": "success", "data": response.json()}
        except Exception:
            return {"status": "success"}

    except requests.exceptions.HTTPError:
        frappe.msgprint(
            f"API request failed with status code {response.status_code}. Response: {response.text}"
        )
        return {"status": "failed", "error": response.text}
    except requests.exceptions.RequestException as e:
        frappe.msgprint(f"API request failed due to a network error: {str(e)}")
        return {"status": "failed", "error": str(e)}


@frappe.whitelist()
def send_subscription_data(doc, method=None):
    if not doc:
        frappe.throw("Subscription Plan is required.")

    target_url, headers = get_project_settings(doc.custom_project)
    if not target_url:
        return

    payload = {
        "doctype": doc.doctype,
        "name": doc.name,
        "plan_name": doc.plan_name,
        "project": doc.custom_project,
        "item": doc.item,
        "trial_days": doc.custom_trial_days,
        "max_users": doc.custom_max_users,
        "max_products": doc.custom_max_products,
        "max_invoices_month": doc.custom_max_invoicesmonth,
        "description": doc.custom_description,
        "reports": doc.custom_reports,
        "active": doc.custom_active,
        "display_order": doc.custom_display_order,
        "price_determination": doc.price_determination,
        "cost": doc.cost,
        "price_list": doc.price_list,
        "billing_interval": doc.billing_interval,
        "billing_interval_count": doc.billing_interval_count,
    }

    return send_api_request(target_url, headers, payload)


@frappe.whitelist()
def send_customer_data(doc, method=None):
    if doc.get("custom_project_company"):
        return

    project = doc.get("custom_project") or ""
    if not project:
        return

    target_url, headers = get_project_settings(project)
    if not target_url:
        return

    first_name = doc.get("first_name") or ""
    last_name = doc.get("last_name") or ""
    owner_name = f"{first_name} {last_name}".strip()

    payload = {
        "doctype": doc.doctype,
        "crm_customer": doc.name,
        "business_name": doc.customer_name,
        "owner_name": owner_name,
        "mobile": doc.get("mobile_no") or "",
        "email": doc.get("email_id") or "",
        "city": doc.get("custom_city") or "",
        "subdomain": doc.get("custom_sub_domain") or "",
        "plan": doc.get("custom_plan") or "",
        "password": doc.get("custom_password") or "",
        "sample_data": 1 if doc.get("custom_sample_data") else 0,
        "activation_start_date": str(doc.get("custom_activation_start_date")) if doc.get("custom_activation_start_date") else "",
        "activation_end_date": str(doc.get("custom_activation_end_date")) if doc.get("custom_activation_end_date") else "",
        "sell_only_products": 1 if doc.get("custom_sell_only_products") else 0,
        "project": project
    }

    res = send_api_request(target_url, headers, payload)

    if res and res.get("status") == "success" and res.get("data"):
        returned_data = res.get("data", {})

        saas_company_code = None
        if isinstance(returned_data, dict):
            saas_company_code = returned_data.get("company_code")
            if not saas_company_code and isinstance(returned_data.get("message"), dict):
                saas_company_code = returned_data["message"].get("company_code")

        if saas_company_code:
            if method == "validate":
                doc.custom_project_company = saas_company_code
            else:
                doc.db_set("custom_project_company", saas_company_code)

    return res


@frappe.whitelist()
def send_crm_invoice_data(doc, method=None):
    if not doc:
        frappe.throw("Invoice is required.")

    project = doc.get("project") or ""
    if not project and doc.customer:
        project = frappe.db.get_value("Customer", doc.customer, "custom_project") or ""

    target_url, headers = get_project_settings(project)
    if not target_url:
        return

    if not target_url:
        frappe.throw("Target URL is not configured.")

    payload = {
        "doctype": "Sales Invoice",
        "saas_company": doc.customer,
        "posting_date": doc.posting_date,
        "due_date": doc.due_date,
        "total_amount": doc.grand_total,
        "status": doc.status,
        "crm_invoice": doc.name,
        "project": project
    }

    return send_api_request(target_url, headers, payload)


@frappe.whitelist()
def validate_crm_deal(doc, method=None):
    if doc.status == "Won":
        if not doc.email and doc.lead:
            doc.email = frappe.db.get_value("CRM Lead", doc.lead, "email")
        if not doc.mobile_no and doc.lead:
            doc.mobile_no = frappe.db.get_value("CRM Lead", doc.lead, "mobile_no")

        mandatory_fields = [
            "first_name", "email", "mobile_no", "custom_city",
            "custom_sub_domain", "custom_plan", "custom_password",
            "custom_project", "custom_activation_start_date", "custom_activation_end_date"
        ]
        missing_labels = [doc.meta.get_label(f) for f in mandatory_fields if not doc.get(f)]
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

    company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company")

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
        frappe.log_error(f"Failed to create Subscription for {doc.name}: {str(e)}", "Customer Subscription")


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

    # Also sync basic fields if empty
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
            frappe.log_error(f"Failed to create CRM Task for Deal {doc.name}: {str(e)}", "CRM Deal Task Creation")


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
            frappe.log_error(f"Failed to create CRM Task for Deal {doc.name}: {str(e)}", "CRM Deal Task Creation")


@frappe.whitelist()
def before_sales_invoice_insert(doc, method=None):
    if doc.get("subscription"):
        if not doc.get("project") and doc.get("customer"):
            project = frappe.db.get_value("Customer", doc.customer, "custom_project")
            if project:
                doc.project = project


@frappe.whitelist()
def send_subscription_status_data(doc, method=None):
    if doc.status == "Active":
        project = frappe.db.get_value("Customer", doc.party, "custom_project") or ""
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
                interval = frappe.db.get_value("Subscription Plan", package, "billing_interval")
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


@frappe.whitelist()
def update_lead_last_call_log(doc, method=None):
    if doc.reference_doctype == "CRM Lead" and doc.reference_docname:
        call_type = "Inbound Call" if doc.type == "Incoming" else "Outbound Call"
        date_str = frappe.utils.format_date(doc.creation, "MMM dd, yyyy")
        status = doc.status or ""
        
        summary = f"{call_type} • {date_str} • {status}"
        
        frappe.db.set_value("CRM Lead", doc.reference_docname, "custom_last_call_log", summary)
