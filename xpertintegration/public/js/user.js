frappe.ui.form.on("User", {
	refresh(frm) {
		if (frm.is_new()) return;

		const has_profile_cs = has_crm_lead_profile(frm.doc);

		frappe.call({
			method: "xpertintegration.api.integration.check_user_sales_and_referral",
			args: { user: frm.doc.name },
			callback: function (r) {
				if (!r.message) return;

				const { has_sales_person, has_referral_code, is_crm_lead_profile } = r.message;

				// Only display buttons if user's role_profiles includes "CRM Lead Profile"
				if (!has_profile_cs && !is_crm_lead_profile) return;

				// Show "Set Commission Rate" if Sales Person record does not exist for the user
				if (!has_sales_person) {
					frm.add_custom_button(__("Set Commission Rate"), function () {
						frappe.prompt(
							[
								{
									label: __("Commission Rate"),
									fieldname: "commission_rate",
									fieldtype: "Data",
									reqd: 1,
									description: __("Enter the commission rate for this sales person.")
								}
							],
							function (values) {
								frappe.call({
									method: "xpertintegration.api.integration.create_sales_person",
									args: {
										user: frm.doc.name,
										commission_rate: values.commission_rate
									},
									freeze: true,
									freeze_message: __("Creating Sales Person..."),
									callback: function (res) {
										if (res.message) {
											frappe.msgprint({
												title: __("Success"),
												indicator: "green",
												message: __("Sales Person {0} created successfully.", [res.message])
											});
											frm.refresh();
										}
									}
								});
							},
							__("Set Commission Rate"),
							__("Save")
						);
					});
				}

				// Show "Set Referral Code" if User Referral Code record does not exist for the user
				if (!has_referral_code) {
					frm.add_custom_button(__("Set Referral Code"), function () {
						frappe.prompt(
							[
								{
									label: __("Referral Code"),
									fieldname: "referral_code",
									fieldtype: "Data",
									reqd: 1,
									description: __("Enter the referral code for this user.")
								}
							],
							function (values) {
								frappe.call({
									method: "xpertintegration.api.integration.create_user_referral_code",
									args: {
										user: frm.doc.name,
										referral_code: values.referral_code
									},
									freeze: true,
									freeze_message: __("Creating User Referral Code..."),
									callback: function (res) {
										if (res.message) {
											frappe.msgprint({
												title: __("Success"),
												indicator: "green",
												message: __("User Referral Code {0} created successfully.", [res.message])
											});
											frm.refresh();
										}
									}
								});
							},
							__("Set Referral Code"),
							__("Save")
						);
					});
				}
			}
		});
	}
});

function has_crm_lead_profile(doc) {
	if (!doc) return false;
	if (doc.role_profile_name === "CRM Lead Profile") return true;
	if (doc.role_profiles && Array.isArray(doc.role_profiles)) {
		return doc.role_profiles.some(
			(row) => row.role_profile === "CRM Lead Profile" || row.role_profile_name === "CRM Lead Profile"
		);
	}
	return false;
}
