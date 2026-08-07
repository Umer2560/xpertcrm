frappe.pages['payment-verification'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Payment Verification',
		single_column: true
	});

	frappe.require('payment_verification.css');

	wrapper.payment_verification_page = new PaymentVerificationPage(wrapper);
}

class PaymentVerificationPage {
	constructor(wrapper) {
		this.wrapper = $(wrapper).find('.layout-main-section');
		this.page = wrapper.page;
		this.load_data();
	}

	load_data() {
		frappe.call({
			method: 'xpertintegration.xpertintegration.page.payment_verification.payment_verification.get_pending_deals',
			callback: (r) => {
				if (r.message) {
					this.render_data(r.message);
				}
			}
		});
	}

	render_data(data) {
		this.wrapper.html(frappe.render_template('payment_verification', { data: data }));
		this.bind_events();
	}

	bind_events() {
		let me = this;
		
		this.wrapper.find('.proof-image').off('click').on('click', function() {
			let url = $(this).data('url');
			let d = new frappe.ui.Dialog({
				title: 'Payment Proof',
				fields: [
					{
						fieldtype: 'HTML',
						fieldname: 'image_html',
						options: `<div class="text-center" style="padding: 10px; background: #f8f9fa; border-radius: 8px;">
									<img src="${url}" style="max-width: 100%; max-height: 65vh; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);" />
								  </div>`
					}
				],
				size: 'large'
			});
			d.show();
		});

		this.wrapper.find('.action-select').off('change').on('change', function() {
			let val = $(this).val();
			let remarks_input = $(this).siblings('.remarks-input');
			if (['Cancelled', 'Unpaid'].includes(val)) {
				remarks_input.show();
			} else {
				remarks_input.hide();
			}
		});

		this.wrapper.find('.btn-save').off('click').on('click', function() {
			let btn = $(this);
			let name = btn.attr('data-name');
			let tr = btn.closest('tr');
			let status = tr.find('.action-select').val();
			let remarks = tr.find('.remarks-input').val();

			if (!status) {
				frappe.msgprint('Please select an action');
				return;
			}

			if (['Cancelled', 'Unpaid'].includes(status) && !remarks) {
				frappe.msgprint('Please provide remarks for ' + status);
				return;
			}

			me.call_update_status(name, status, remarks);
		});
	}

	call_update_status(name, status, remarks) {
		frappe.call({
			method: 'xpertintegration.xpertintegration.page.payment_verification.payment_verification.update_deal_status',
			args: {
				name: name,
				status: status,
				remarks: remarks
			},
			callback: (r) => {
				if (!r.exc) {
					frappe.show_alert({message: 'Saved Successfully', indicator: 'green'});
					this.load_data();
				}
			}
		});
	}
}