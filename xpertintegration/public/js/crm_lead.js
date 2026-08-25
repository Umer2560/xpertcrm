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

		if (frm.doc.custom_fetch_company) {
			frm.add_custom_button(__("Fetch Company Data"), function () {
				trigger_fetch_company_details(frm);
			}, __("Actions"));
		}
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
	custom_fetch_company(frm) {
		frm.toggle_display(["custom_company_code", "custom_project", "lead_owner"], !!frm.doc.custom_fetch_company);
		if (frm.doc.custom_fetch_company) {
			frappe.show_alert({
				message: __("Enter Company Code and Project, then click 'Fetch Company Data' or Save."),
				indicator: "blue"
			});
		}
	},
});

function trigger_fetch_company_details(frm) {
	if (!frm.doc.custom_company_code || !frm.doc.custom_project) {
		frappe.msgprint(__("Please enter both Company Code and Project before fetching details."));
		return;
	}

	frappe.call({
		method: "xpertintegration.api.integration.fetch_company_details_from_project",
		args: {
			company_code: frm.doc.custom_company_code,
			custom_company_code: frm.doc.custom_company_code,
			project: frm.doc.custom_project,
			lead_id: frm.is_new() ? null : frm.doc.name
		},
		freeze: true,
		freeze_message: __("Fetching Company Details from Project..."),
		callback: function (r) {
			if (r && r.message && r.message.status === "success") {
				frappe.show_alert({
					message: r.message.message || __("Company details fetched successfully!"),
					indicator: "green"
				});
				if (!frm.is_new()) {
					frm.reload_doc();
				} else {
					var data = r.message.data || {};
					if (data.company_name || data.organization || data.name) {
						frm.set_value("organization", data.company_name || data.organization || data.name);
					}
					if (data.first_name) frm.set_value("first_name", data.first_name);
					if (data.last_name) frm.set_value("last_name", data.last_name);
					if (data.email) frm.set_value("email", data.email);
					if (data.mobile_no || data.mobile) frm.set_value("mobile_no", data.mobile_no || data.mobile);
					if (data.phone) frm.set_value("phone", data.phone);
					if (data.website) frm.set_value("website", data.website);
					if (data.city || data.custom_city) frm.set_value("custom_city", data.city || data.custom_city);
					if (data.territory) frm.set_value("territory", data.territory);
					if (data.industry) frm.set_value("industry", data.industry);
					if (data.sub_domain || data.custom_sub_domain) frm.set_value("custom_sub_domain", data.sub_domain || data.custom_sub_domain);
					if (data.custom_plan || data.plan) frm.set_value("custom_plan", data.custom_plan || data.plan);
					frm.refresh_fields();
				}
			}
		}
	});
}

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
