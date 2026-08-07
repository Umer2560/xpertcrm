import frappe

@frappe.whitelist()
def test_update_no_name():
    doc_fields = {
        "__unsaved": 1,
        "company": "RaabtaX",
        "doctype": "Subscription",
        "name": "ACC-SUB-2026-00056",
        "plans": [{"custom_cost": 400.0, "doctype": "Subscription Plan Detail", "idx": 1, "parent": "ACC-SUB-2026-00056", "parentfield": "plans", "parenttype": "Subscription", "plan": "Test Plan 003", "qty": 1}],
    }
    try:
        doc = frappe.get_doc("Subscription", "ACC-SUB-2026-00056")
        doc.update(doc_fields)
        doc.save(ignore_permissions=True)
        print("Update Success")
    except Exception as e:
        import traceback
        print(traceback.format_exc())

test_update_no_name()
