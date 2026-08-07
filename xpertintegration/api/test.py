import frappe

def test_insert_exact():
    doc_fields = {"__unsaved": 1, "additional_discount_amount": 0.0, "additional_discount_percentage": 0.0, "apply_additional_discount": "", "cancel_at_period_end": 0, "cancelation_date": None, "company": "RaabtaX", "cost_center": "Main - RX", "current_invoice_end": "2026-09-05", "current_invoice_start": "2026-08-06", "custom_amount_paid": 0.0, "custom_cost": 2000.0, "custom_project": "SaleDesk", "days_until_due": 0, "docstatus": 0, "doctype": "Subscription", "end_date": None, "follow_calendar_months": 0, "generate_invoice_at": "End of the current subscription period", "generate_new_invoices_past_due_date": 0, "idx": 0, "number_of_days": 0, "party": "Azfar Halwa Center", "party_type": "Customer", "plans": [{"__unsaved": 1, "custom_cost": 400.0, "docstatus": 0, "doctype": "Subscription Plan Detail", "idx": 1, "parent": "ACC-SUB-2026-00060", "parentfield": "plans", "parenttype": "Subscription", "plan": "Test Plan 003", "qty": 1}], "purchase_tax_template": None, "sales_tax_template": None, "start_date": "2026-08-06", "status": "Active", "submit_invoice": 1, "trial_period_end": None, "trial_period_start": None}
    try:
        doc = frappe.get_doc(doc_fields)
        doc.insert(ignore_permissions=True)
        print("Insert Success")
    except Exception as e:
        import traceback
        print(traceback.format_exc())

test_insert_exact()
