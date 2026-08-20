frappe.ui.form.on("CRM Lead", {
	setup(frm) {
		frm.set_query("custom_plan", function () {
			return {
				filters: {
					custom_project: frm.doc.custom_project || "",
					custom_subscription_type: ["!=", "Addons"],
					custom_active: 1,
				},
			};
		});
		frm.set_query("add_on", "custom_addons_table", function (doc, cdt, cdn) {
			return {
				filters: {
					custom_project: frm.doc.custom_project || "",
					custom_subscription_type: "Addons",
					custom_active: 1,
				},
			};
		});
	},
	refresh(frm) {
		check_lead_duplicates(frm);
		frm.set_query("custom_plan", function () {
			return {
				filters: {
					custom_project: frm.doc.custom_project || "",
					custom_subscription_type: ["!=", "Addons"],
					custom_active: 1,
				},
			};
		});
		frm.set_query("add_on", "custom_addons_table", function (doc, cdt, cdn) {
			return {
				filters: {
					custom_project: frm.doc.custom_project || "",
					custom_subscription_type: "Addons",
					custom_active: 1,
				},
			};
		});
	},
	email(frm) {
		check_lead_duplicates(frm);
	},
	mobile_no(frm) {
		check_lead_duplicates(frm);
	},
	custom_project(frm) {
		frm.set_value("custom_plan", "");
	},
});

function check_lead_duplicates(frm) {
	if (!frm.doc.email && !frm.doc.mobile_no) {
		frm.set_df_property("email", "description", "");
		frm.set_df_property("mobile_no", "description", "");
		return;
	}

	frappe.call({
		method: "xpertintegration.api.integration.check_lead_duplicates",
		args: {
			email: frm.doc.email,
			mobile_no: frm.doc.mobile_no,
			lead_id: frm.doc.name,
		},
		callback: function (r) {
			if (r && r.message) {
				if (r.message.email_exists) {
					frm.set_df_property(
						"email",
						"description",
						"<span style='color: #d97706; font-weight: 500;'>⚠️ " +
							r.message.email_message +
							"</span>"
					);
				} else {
					frm.set_df_property("email", "description", "");
				}

				if (r.message.mobile_exists) {
					frm.set_df_property(
						"mobile_no",
						"description",
						"<span style='color: #d97706; font-weight: 500;'>⚠️ " +
							r.message.mobile_message +
							"</span>"
					);
				} else {
					frm.set_df_property("mobile_no", "description", "");
				}
			}
		},
	});
}
