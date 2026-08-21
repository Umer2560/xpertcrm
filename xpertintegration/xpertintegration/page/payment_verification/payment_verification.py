import frappe
from frappe.utils import flt, formatdate
from xpertintegration.api.integration import create_integration_log, log_integration_error


@frappe.whitelist()
def get_pending_verification_records(
    payment_type="All",
    customer=None,
    project=None,
    crm_deal=None,
    payment_entry=None,
):
    records = []
    fetch_deals = payment_type in ["All", "Deal Invoice Payment", "", None]
    fetch_pes = payment_type in ["All", "Sales Invoice Payment", "", None]

    if customer:
        fetch_deals = False
        fetch_pes = True

    if fetch_deals:
        filters = {"custom_payment_status": "Verify Payment"}
        if project:
            filters["custom_project"] = project
        if crm_deal and payment_type == "Deal Invoice Payment":
            filters["name"] = crm_deal

        or_filters = None
        if customer:
            or_filters = [
                ["CRM Deal", "erpnext_customer", "=", customer],
                ["CRM Deal", "custom_company_code", "=", customer],
                ["CRM Deal", "organization", "=", customer],
            ]

        deals = frappe.get_all(
            "CRM Deal",
            filters=filters,
            or_filters=or_filters,
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
                "custom_mode_of_payment",
                "custom_account_paid_to",
                "custom_project",
                "custom_payment_remarks",
                "modified",
            ],
            limit=100,
            order_by="modified desc",
        )

        date_fields = ["custom_posting_date", "custom_payment_date", "custom_due_date"]
        for deal in deals:
            deal["record_type"] = "Deal Invoice Payment"
            deal["link"] = f"/app/crm-deal/{deal['name']}"
            deal["title_label"] = (
                deal.get("organization") or deal.get("custom_company_code") or "-"
            )
            for f in date_fields:
                if deal.get(f):
                    deal[f] = formatdate(deal[f], "dd-MMM-yyyy")
            records.append(deal)

    if fetch_pes:
        filters = {"docstatus": 0}  # Draft payment entries
        if payment_entry and payment_type == "Sales Invoice Payment":
            filters["name"] = payment_entry

        if customer:
            filters["party"] = customer

        meta = frappe.get_meta("Payment Entry")
        fieldnames = [f.fieldname for f in meta.fields]

        if project:
            if "custom_project_payment" in fieldnames:
                filters["custom_project_payment"] = project
            elif "project" in fieldnames:
                filters["project"] = project

        pe_fields = [
            "name",
            "party_type",
            "party",
            "party_name",
            "paid_amount",
            "received_amount",
            "posting_date",
            "reference_no",
            "reference_date",
            "mode_of_payment",
            "paid_to",
            "docstatus",
            "modified",
        ]
        if "custom_payment_proof" in fieldnames:
            pe_fields.append("custom_payment_proof")
        if "custom_payment_remarks" in fieldnames:
            pe_fields.append("custom_payment_remarks")

        pes = frappe.get_all(
            "Payment Entry",
            filters=filters,
            fields=pe_fields,
            limit=100,
            order_by="modified desc",
        )

        for pe in pes:
            proof_url = pe.get("custom_payment_proof")
            if not proof_url:
                attached_file = frappe.db.get_value(
                    "File",
                    {"attached_to_doctype": "Payment Entry", "attached_to_name": pe["name"]},
                    "file_url",
                )
                if attached_file:
                    proof_url = attached_file

            posting_fmt = (
                formatdate(pe.get("posting_date"), "dd-MMM-yyyy")
                if pe.get("posting_date")
                else ""
            )
            ref_fmt = (
                formatdate(pe.get("reference_date"), "dd-MMM-yyyy")
                if pe.get("reference_date")
                else ""
            )

            rec = {
                "name": pe["name"],
                "record_type": "Sales Invoice Payment",
                "link": f"/app/payment-entry/{pe['name']}",
                "organization": pe.get("party_name") or pe.get("party") or "-",
                "custom_company_code": pe.get("party_type") or "Draft Payment Entry",
                "mobile_no": "",
                "custom_reference_number": pe.get("reference_no") or pe.get("name"),
                "custom_posting_date": posting_fmt,
                "custom_payment_date": ref_fmt or posting_fmt,
                "custom_due_date": "",
                "custom_amount": flt(pe.get("paid_amount")),
                "custom_paid_amount": flt(pe.get("received_amount") or pe.get("paid_amount")),
                "custom_payment_proof": proof_url,
                "custom_mode_of_payment": pe.get("mode_of_payment"),
                "custom_account_paid_to": pe.get("paid_to"),
                "custom_payment_status": "Verify Payment",
                "custom_payment_remarks": pe.get("custom_payment_remarks") or "",
                "modified": pe.get("modified"),
            }
            records.append(rec)

    records.sort(key=lambda x: str(x.get("modified") or ""), reverse=True)
    return records


@frappe.whitelist()
def get_pending_deals():
    """Alias for backward compatibility."""
    return get_pending_verification_records(payment_type="All")


@frappe.whitelist()
def update_verification_record(
    record_type,
    name,
    status,
    remarks=None,
    amount_received=None,
    mode_of_payment=None,
    account_paid_to=None,
):
    if record_type == "Deal Invoice Payment":
        return update_deal_status(
            name, status, remarks, amount_received, mode_of_payment, account_paid_to
        )

    elif record_type == "Sales Invoice Payment":
        if not frappe.db.exists("Payment Entry", name):
            frappe.throw(f"Payment Entry {name} does not exist.")

        pe = frappe.get_doc("Payment Entry", name)
        if pe.docstatus != 0:
            frappe.throw(f"Payment Entry {name} is not in Draft status.")

        val = (
            flt(amount_received)
            if amount_received is not None and str(amount_received).strip() != ""
            else pe.paid_amount
        )

        if val > 0:
            pe.paid_amount = val
            pe.received_amount = val

            if pe.references:
                remaining = val
                for ref in pe.references:
                    if ref.outstanding_amount:
                        alloc = min(remaining, flt(ref.outstanding_amount))
                    else:
                        alloc = remaining
                    ref.allocated_amount = alloc
                    remaining -= alloc
                if remaining > 0 and len(pe.references) > 0:
                    pe.references[0].allocated_amount = flt(pe.references[0].allocated_amount) + remaining

        if mode_of_payment:
            pe.mode_of_payment = mode_of_payment
        if account_paid_to:
            pe.paid_to = account_paid_to

        pe.flags.ignore_permissions = True

        if status == "Paid":
            pe.save()
            pe.submit()
            frappe.msgprint(
                f"Payment Entry {name} Verified & Submitted with Received Amount {val}",
                alert=True,
                indicator="green",
            )
        elif status in ["Cancelled", "Unpaid"]:
            if hasattr(pe, "custom_payment_remarks"):
                pe.custom_payment_remarks = remarks
            pe.save()
            if status == "Cancelled":
                pe.cancel()
            frappe.msgprint(
                f"Payment Entry {name} marked as {status}",
                alert=True,
                indicator="orange",
            )

        return True

    return False


@frappe.whitelist()
def update_deal_status(
    name,
    status,
    remarks=None,
    amount_received=None,
    mode_of_payment=None,
    account_paid_to=None,
):
    fields_to_update = {"custom_payment_status": status}
    if remarks:
        fields_to_update["custom_payment_remarks"] = remarks

    if amount_received is not None:
        fields_to_update["custom_paid_amount"] = amount_received

    if mode_of_payment:
        fields_to_update["custom_mode_of_payment"] = mode_of_payment

    if account_paid_to:
        fields_to_update["custom_account_paid_to"] = account_paid_to

    if status in ["Paid", "Submitted"]:
        fields_to_update["custom_payment_status"] = "Submitted"
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

    if status in ["Paid", "Submitted"]:
        from xpertintegration.api.integration import process_deal_billing_pipeline
        process_deal_billing_pipeline(doc)

    return True

