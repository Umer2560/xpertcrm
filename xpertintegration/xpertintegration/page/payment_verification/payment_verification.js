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
		this.current_page = 1;
		this.page_size = 10;
		this.all_data = [];
		this.load_data();
	}

	load_data() {
		frappe.call({
			method: 'xpertintegration.xpertintegration.page.payment_verification.payment_verification.get_pending_deals',
			callback: (r) => {
				if (r.message) {
					this.all_data = r.message;
					this.current_page = 1;
					this.render_page();
				}
			}
		});
	}

	render_page() {
		let start = (this.current_page - 1) * this.page_size;
		let end = start + this.page_size;
		let page_data = this.all_data.slice(start, end);
		let total_pages = Math.ceil(this.all_data.length / this.page_size);

		this.wrapper.html(frappe.render_template('payment_verification', { 
			data: page_data,
			current_page: this.current_page,
			total_pages: total_pages,
			total_records: this.all_data.length
		}));
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
			let tr = btn.closest('.pv-card');
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

		// Pagination Events
		this.wrapper.find('.btn-prev').off('click').on('click', () => {
			if (this.current_page > 1) {
				this.current_page--;
				this.render_page();
			}
		});

		this.wrapper.find('.btn-next').off('click').on('click', () => {
			let total_pages = Math.ceil(this.all_data.length / this.page_size);
			if (this.current_page < total_pages) {
				this.current_page++;
				this.render_page();
			}
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