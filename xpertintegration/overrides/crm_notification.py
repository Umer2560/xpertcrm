import frappe


def get_permission_query_conditions(user=None):
	if not user:
		user = frappe.session.user

	roles = frappe.get_roles(user)
	if user == "Administrator" or "System Manager" in roles or "Sales Manager" in roles:
		return ""

	return f"`tabCRM Notification`.`to_user` = {frappe.db.escape(user)}"


def has_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user

	roles = frappe.get_roles(user)
	if user == "Administrator" or "System Manager" in roles or "Sales Manager" in roles:
		return True

	if ptype == "create" or not doc.to_user:
		return True

	return doc.to_user == user


def apply_crm_notification_override():
	try:
		import crm.fcrm.doctype.crm_notification.crm_notification as target_module

		target_module.get_permission_query_conditions = get_permission_query_conditions
		target_module.has_permission = has_permission
	except Exception as e:
		frappe.log_error(f"Failed to apply CRM Notification override: {e}", "CRM Notification Override Error")


# Apply override on module load
apply_crm_notification_override()
