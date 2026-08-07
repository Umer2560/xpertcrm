import frappe

@frappe.whitelist()
def test_update():
    doc_fields = {
        "__unsaved": 1,
        "company": "RaabtaX",
        "doctype": "Subscription",
        "name": "ACC-SUB-2026-00056",
        "party": "Azfar Halwa Center",
        "party_type": "Customer",
        "plans": [{"custom_cost": 400.0, "doctype": "Subscription Plan Detail", "idx": 1, "parent": "ACC-SUB-2026-00056", "parentfield": "plans", "parenttype": "Subscription", "plan": "Test Plan 003", "qty": 1}],
        "start_date": "2026-08-06",
        "status": "Grace Period"
    }
    try:
        if frappe.db.exists("Subscription", "ACC-SUB-2026-00056"):
            doc = frappe.get_doc("Subscription", "ACC-SUB-2026-00056")
            doc.update(doc_fields)
            doc.save(ignore_permissions=True)
            print("Update Success")
        else:
            print("Sub not found")
    except Exception as e:
        import traceback
        print(traceback.format_exc())

test_update()
