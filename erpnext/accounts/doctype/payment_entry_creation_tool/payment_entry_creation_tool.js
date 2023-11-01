// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Payment Entry Creation Tool', {
	refresh: function(frm) {
		if (!frm.is_new() && !frm.doc.completed) {
			frm.disable_save();
			frm.add_custom_button(__("Create Payment Entries"), function () {
				frappe.call({
					method: "create_payment_entries",
					doc: frm.doc,
					callback: function(r) {
					}
				});
			});
		}
		if(frm.doc.completed) {
			frm.disable_save();
		}
	}
});
