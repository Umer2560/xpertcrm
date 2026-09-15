import frappe
from frappe import _
from frappe.utils import flt, formatdate, getdate, today
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from xpertintegration.api.integration import create_integration_log, log_integration_error


@frappe.whitelist()
def get_unlinked_sales_invoices(customer=None, project=None, search_term=None, status=None):
    """
    Fetches Sales Invoices where:
    - custom_crm_deal is empty / null
    - payment status is not paid and not cancelled (status NOT IN ('Paid', 'Cancelled')) by default,
      or matches the specific status filter if provided.
    Also checks if a draft Payment Entry already exists for the invoice.
    """
    conditions = []
    params = {}

    if status and str(status).strip():
        st = str(status).strip()
        conditions.append("si.status = %(status)s")
        params["status"] = st
        if st == "Cancelled":
            conditions.append("si.docstatus = 2")
        elif st == "Draft":
            conditions.append("si.docstatus = 0")
        else:
            conditions.append("si.docstatus = 1")
    else:
        conditions.append("si.docstatus = 1")
        conditions.append("si.status NOT IN ('Paid', 'Cancelled')")
        conditions.append("si.outstanding_amount > 0")

    conditions.append("""
        NOT EXISTS (
            SELECT 1 
            FROM `tabPayment Entry Reference` per 
            JOIN `tabPayment Entry` pe ON pe.name = per.parent 
            WHERE per.reference_doctype = 'Sales Invoice' 
              AND per.reference_name = si.name 
              AND pe.docstatus = 0
        )
    """)

    if customer:
        conditions.append("si.customer = %(customer)s")
        params["customer"] = customer

    if project:
        conditions.append("(si.project = %(project)s OR si.custom_project_company = %(project)s)")
        params["project"] = project

    if search_term and search_term.strip():
        conditions.append(
            "(si.name LIKE %(search)s OR si.customer LIKE %(search)s OR si.customer_name LIKE %(search)s)"
        )
        params["search"] = f"%{search_term.strip()}%"

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            si.name,
            si.customer,
            si.customer_name,
            si.posting_date,
            si.due_date,
            si.grand_total,
            si.outstanding_amount,
            si.status,
            si.project,
            si.custom_project_company,
            si.subscription,
            si.custom_plan,
            si.contact_mobile,
            si.contact_email,
            si.currency,
            si.modified,
            (
                SELECT pe.name 
                FROM `tabPayment Entry Reference` per 
                JOIN `tabPayment Entry` pe ON pe.name = per.parent 
                WHERE per.reference_doctype = 'Sales Invoice' 
                  AND per.reference_name = si.name 
                  AND pe.docstatus = 0 
                LIMIT 1
            ) AS draft_payment_entry
        FROM `tabSales Invoice` si
        WHERE {where_clause}
        ORDER BY si.modified DESC
        LIMIT 200
    """

    invoices = frappe.db.sql(query, params, as_dict=True)

    records = []
    for inv in invoices:
        posting_fmt = formatdate(inv.posting_date, "dd-MMM-yyyy") if inv.posting_date else ""
        due_fmt = formatdate(inv.due_date, "dd-MMM-yyyy") if inv.due_date else ""

        records.append(
            {
                "name": inv.name,
                "link": f"/app/sales-invoice/{inv.name}",
                "customer": inv.customer,
                "customer_name": inv.customer_name or inv.customer or "-",
                "posting_date": posting_fmt,
                "due_date": due_fmt,
                "raw_posting_date": str(inv.posting_date) if inv.posting_date else str(today()),
                "grand_total": flt(inv.grand_total),
                "outstanding_amount": flt(inv.outstanding_amount),
                "status": inv.status,
                "status_slug": (inv.status or "").lower().replace(" ", "-"),
                "project": inv.project or inv.custom_project_company or "-",
                "subscription": inv.subscription or "-",
                "custom_plan": inv.custom_plan or "-",
                "contact_mobile": inv.contact_mobile or "",
                "contact_email": inv.contact_email or "",
                "currency": inv.currency or "PKR",
                "modified": str(inv.modified),
                "draft_payment_entry": inv.draft_payment_entry or "",
            }
        )

    return records


@frappe.whitelist()
def get_draft_payment_entries(customer=None, project=None, search_term=None):
    """
    Fetches all Payment Entries in Draft state (docstatus = 0) created for Sales Invoices.
    """
    conditions = [
        "pe.docstatus = 0",
        "pe.payment_type = 'Receive'",
    ]
    params = {}

    if customer:
        conditions.append("pe.party = %(customer)s")
        params["customer"] = customer

    if search_term and search_term.strip():
        conditions.append(
            "(pe.name LIKE %(search)s OR pe.party LIKE %(search)s OR pe.party_name LIKE %(search)s OR per.reference_name LIKE %(search)s)"
        )
        params["search"] = f"%{search_term.strip()}%"

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            pe.name,
            pe.party AS customer,
            pe.party_name AS customer_name,
            pe.posting_date,
            pe.reference_no,
            pe.reference_date,
            pe.paid_amount,
            pe.mode_of_payment,
            pe.paid_to AS account_paid_to,
            pe.remarks,
            pe.modified,
            per.reference_name AS sales_invoice
        FROM `tabPayment Entry` pe
        LEFT JOIN `tabPayment Entry Reference` per ON per.parent = pe.name AND per.reference_doctype = 'Sales Invoice'
        WHERE {where_clause}
        ORDER BY pe.modified DESC
        LIMIT 200
    """

    entries = frappe.db.sql(query, params, as_dict=True)

    records = []
    for pe_row in entries:
        # Check payment proof if exists
        proof = getattr(pe_row, "custom_payment_proof", None)
        if not proof:
            # Check attached files
            attached_file = frappe.db.get_value(
                "File",
                {"attached_to_doctype": "Payment Entry", "attached_to_name": pe_row.name},
                "file_url",
            )
            proof = attached_file or ""

        posting_fmt = formatdate(pe_row.posting_date, "dd-MMM-yyyy") if pe_row.posting_date else ""
        currency = frappe.db.get_default("currency") or "PKR"

        records.append(
            {
                "name": pe_row.name,
                "link": f"/app/payment-entry/{pe_row.name}",
                "sales_invoice": pe_row.sales_invoice or "",
                "sales_invoice_link": f"/app/sales-invoice/{pe_row.sales_invoice}" if pe_row.sales_invoice else "",
                "customer": pe_row.customer or "",
                "customer_name": pe_row.customer_name or pe_row.customer or "-",
                "posting_date": posting_fmt,
                "raw_posting_date": str(pe_row.posting_date) if pe_row.posting_date else str(today()),
                "paid_amount": flt(pe_row.paid_amount),
                "reference_number": pe_row.reference_no or "",
                "mode_of_payment": pe_row.mode_of_payment or "",
                "account_paid_to": pe_row.account_paid_to or "",
                "payment_proof": proof,
                "remarks": pe_row.remarks or "",
                "currency": currency,
                "modified": str(pe_row.modified),
            }
        )

    return records


@frappe.whitelist()
def create_payment_entry_for_invoice(
    sales_invoice,
    paid_amount,
    payment_date=None,
    reference_number=None,
    payment_proof=None,
    mode_of_payment=None,
    account_paid_to=None,
    remarks=None,
):
    """
    Creates a Payment Entry in Draft state (docstatus = 0) for an unlinked Sales Invoice.
    """
    if not sales_invoice or not frappe.db.exists("Sales Invoice", sales_invoice):
        frappe.throw(_("Sales Invoice {0} does not exist.").format(sales_invoice))

    si_doc = frappe.get_doc("Sales Invoice", sales_invoice)
    if si_doc.docstatus != 1:
        frappe.throw(_("Sales Invoice {0} is not submitted.").format(sales_invoice))

    if flt(si_doc.outstanding_amount) <= 0:
        frappe.throw(_("Sales Invoice {0} has no outstanding amount.").format(sales_invoice))

    amount = flt(paid_amount)
    if amount <= 0:
        frappe.throw(_("Payment Amount must be greater than 0."))

    pay_date = getdate(payment_date) if payment_date else getdate(today())

    try:
        pe = get_payment_entry("Sales Invoice", sales_invoice, bank_account=account_paid_to)
        pe.paid_amount = amount
        pe.received_amount = amount
        pe.posting_date = pay_date
        pe.reference_date = pay_date

        if reference_number and str(reference_number).strip():
            pe.reference_no = str(reference_number).strip()
        else:
            pe.reference_no = f"PAY-{sales_invoice}"

        if mode_of_payment:
            pe.mode_of_payment = mode_of_payment
        if account_paid_to:
            pe.paid_to = account_paid_to

        if remarks and str(remarks).strip():
            if hasattr(pe, "custom_payment_remarks"):
                pe.custom_payment_remarks = remarks
            pe.remarks = remarks
            pe.custom_remarks = 1
        else:
            if hasattr(pe, "custom_payment_remarks"):
                pe.custom_payment_remarks = ""
            pe.remarks = ""
            pe.custom_remarks = 1

        if payment_proof:
            if hasattr(pe, "custom_payment_proof"):
                pe.custom_payment_proof = payment_proof

        for ref in pe.references:
            if ref.reference_name == sales_invoice:
                ref.allocated_amount = amount

        pe.flags.ignore_permissions = True
        pe.insert(ignore_permissions=True)
        # Note: Saved in Draft mode (docstatus = 0)

        # Link file if payment_proof is provided
        if payment_proof:
            file_docs = frappe.get_all("File", filters={"file_url": payment_proof})
            for f in file_docs:
                frappe.db.set_value(
                    "File",
                    f.name,
                    {
                        "attached_to_doctype": "Payment Entry",
                        "attached_to_name": pe.name,
                    },
                )

        create_integration_log(
            status="Success",
            direction="Inbound",
            trigger_source="Manual Trigger",
            reference_doctype="Payment Entry",
            reference_name=pe.name,
            remarks=f"Draft Payment Entry {pe.name} created for Sales Invoice {sales_invoice} with amount {amount}",
        )

        return {
            "success": True,
            "payment_entry": pe.name,
            "message": _("Draft Payment Entry {0} created successfully for {1}.").format(
                pe.name, sales_invoice
            ),
        }

    except Exception as e:
        log_integration_error(
            title=f"Failed to create Draft Payment Entry for {sales_invoice}",
            message=frappe.get_traceback(),
            reference_doctype="Sales Invoice",
            reference_name=sales_invoice,
        )
        frappe.throw(_("Error creating Draft Payment Entry: {0}").format(str(e)))


@frappe.whitelist()
def update_draft_payment_entry(
    payment_entry,
    paid_amount,
    payment_date=None,
    reference_number=None,
    payment_proof=None,
    mode_of_payment=None,
    account_paid_to=None,
    remarks=None,
):
    """
    Updates an existing Draft Payment Entry (docstatus = 0).
    """
    if not payment_entry or not frappe.db.exists("Payment Entry", payment_entry):
        frappe.throw(_("Payment Entry {0} does not exist.").format(payment_entry))

    pe = frappe.get_doc("Payment Entry", payment_entry)
    if pe.docstatus != 0:
        frappe.throw(_("Payment Entry {0} is not in Draft state and cannot be updated.").format(payment_entry))

    amount = flt(paid_amount)
    if amount <= 0:
        frappe.throw(_("Payment Amount must be greater than 0."))

    pay_date = getdate(payment_date) if payment_date else getdate(today())

    try:
        pe.paid_amount = amount
        pe.received_amount = amount
        pe.posting_date = pay_date
        pe.reference_date = pay_date

        if reference_number and str(reference_number).strip():
            pe.reference_no = str(reference_number).strip()

        if mode_of_payment:
            pe.mode_of_payment = mode_of_payment
        if account_paid_to:
            pe.paid_to = account_paid_to

        if remarks is not None:
            if hasattr(pe, "custom_payment_remarks"):
                pe.custom_payment_remarks = remarks
            pe.remarks = remarks
            pe.custom_remarks = 1

        if payment_proof:
            if hasattr(pe, "custom_payment_proof"):
                pe.custom_payment_proof = payment_proof

        for ref in pe.references:
            ref.allocated_amount = amount

        pe.flags.ignore_permissions = True
        pe.save(ignore_permissions=True)

        if payment_proof:
            file_docs = frappe.get_all("File", filters={"file_url": payment_proof})
            for f in file_docs:
                frappe.db.set_value(
                    "File",
                    f.name,
                    {
                        "attached_to_doctype": "Payment Entry",
                        "attached_to_name": pe.name,
                    },
                )

        return {
            "success": True,
            "payment_entry": pe.name,
            "message": _("Draft Payment Entry {0} updated successfully.").format(pe.name),
        }

    except Exception as e:
        frappe.throw(_("Error updating Draft Payment Entry {0}: {1}").format(payment_entry, str(e)))


@frappe.whitelist()
def submit_draft_payment_entry(payment_entry):
    """
    Submits an existing Draft Payment Entry (docstatus = 0).
    """
    if not payment_entry or not frappe.db.exists("Payment Entry", payment_entry):
        frappe.throw(_("Payment Entry {0} does not exist.").format(payment_entry))

    pe = frappe.get_doc("Payment Entry", payment_entry)
    if pe.docstatus != 0:
        frappe.throw(_("Payment Entry {0} is already submitted or cancelled.").format(payment_entry))

    try:
        pe.flags.ignore_permissions = True
        pe.submit()

        create_integration_log(
            status="Success",
            direction="Inbound",
            trigger_source="Manual Trigger",
            reference_doctype="Payment Entry",
            reference_name=pe.name,
            remarks=f"Draft Payment Entry {pe.name} submitted successfully.",
        )

        return {
            "success": True,
            "payment_entry": pe.name,
            "message": _("Payment Entry {0} submitted successfully.").format(pe.name),
        }

    except Exception as e:
        log_integration_error(
            title=f"Failed to submit Payment Entry {payment_entry}",
            message=frappe.get_traceback(),
            reference_doctype="Payment Entry",
            reference_name=payment_entry,
        )
        frappe.throw(_("Error submitting Payment Entry {0}: {1}").format(payment_entry, str(e)))


@frappe.whitelist()
def delete_draft_payment_entry(payment_entry):
    """
    Deletes a Draft Payment Entry (docstatus = 0).
    """
    if not payment_entry or not frappe.db.exists("Payment Entry", payment_entry):
        frappe.throw(_("Payment Entry {0} does not exist.").format(payment_entry))

    pe = frappe.get_doc("Payment Entry", payment_entry)
    if pe.docstatus != 0:
        frappe.throw(_("Payment Entry {0} is not in Draft state and cannot be deleted.").format(payment_entry))

    try:
        pe.flags.ignore_permissions = True
        pe.delete(ignore_permissions=True)

        return {
            "success": True,
            "message": _("Draft Payment Entry {0} deleted successfully.").format(payment_entry),
        }

    except Exception as e:
        frappe.throw(_("Error deleting Draft Payment Entry {0}: {1}").format(payment_entry, str(e)))
