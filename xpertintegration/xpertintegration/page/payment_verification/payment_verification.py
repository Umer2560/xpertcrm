import frappe


@frappe.whitelist()
def get_pending_deals():
    deals = frappe.get_all(
        "CRM Deal",
        filters={"custom_payment_status": "Verify Payment"},
        fields=[
            "name",
            "lead_name",
            "organization",
            "custom_company_code",
            "mobile_no",
            "custom_amount",
            "custom_payment_proof",
            "custom_payment_status",
            "custom_reference_number",
            "custom_posting_date",
            "custom_payment_date",
            "custom_due_date",
            "custom_paid_amount",
            "custom_amount_received",
            "custom_mode_of_payment",
            "custom_account_paid_to",
        ],
        limit=100,
    )

    date_fields = ["custom_posting_date", "custom_payment_date", "custom_due_date"]
    for deal in deals:
        for f in date_fields:
            if deal.get(f):
                deal[f] = frappe.utils.formatdate(deal[f], "dd-MMM-yyyy")

    return deals


@frappe.whitelist()
def update_deal_status(name, status, remarks=None, amount_received=None, mode_of_payment=None, account_paid_to=None):
    fields_to_update = {"custom_payment_status": status}
    if remarks:
        fields_to_update["custom_payment_remarks"] = remarks

    if amount_received is not None:
        fields_to_update["custom_amount_received"] = amount_received
        fields_to_update["custom_paid_amount"] = amount_received

    if mode_of_payment:
        fields_to_update["custom_mode_of_payment"] = mode_of_payment

    if account_paid_to:
        fields_to_update["custom_account_paid_to"] = account_paid_to

    if status == "Paid":
        fields_to_update["status"] = "Won"

    doc = frappe.get_doc("CRM Deal", name)
    try:
        doc.reload()
    except Exception:
        pass
    doc.update(fields_to_update)
    doc.save(ignore_permissions=True)
    try:
        doc.reload()
    except Exception:
        pass
    if status == "Paid":
        try:
            from crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings import (
                create_customer_from_deal,
            )

            settings = frappe.get_single("ERPNext CRM Settings")
            create_customer_from_deal(doc, settings)
        except Exception as e:
            frappe.log_error("Payment Verification - Customer Creation Failed", str(e))

    # Send specific minimal payload to POS
    # try:
    #     from xpertintegration.api.integration import send_api_request

    #     project = frappe.db.get_value("CRM Deal", name, "custom_project")

    #     setting = frappe.db.get_value(
    #         "XpertIntegration Setting Table",
    #         {"project": project},
    #         ["base_url", "api_key", "api_secret"],
    #         as_dict=True,
    #     )
    #     if setting and setting.base_url and setting.api_key and setting.api_secret:
    #         payload = {
    #             "doctype": "CRM Deal",
    #             "name": name,
    #             "custom_payment_status": status,
    #             "custom_payment_remarks": remarks or "",
    #             "payment_status": status,
    #         }
    #         target_url = f"{setting.base_url.rstrip('/')}/api/method/xpertintegration.api.integration.process_incoming_integration_payload"
    #         headers = {
    #             "Authorization": f"token {setting.api_key}:{setting.api_secret}",
    #             "Content-Type": "application/json",
    #             "Accept": "application/json",
    #         }
    #         send_api_request(target_url, headers, payload, "CRM Deal", name)
    # except Exception as e:
    #     frappe.log_error("Payment Verification Sync Failed", str(e))

    return True
