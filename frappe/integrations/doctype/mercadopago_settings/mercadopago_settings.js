// Copyright (c) 2021, Frappe Technologies and contributors
// For license information, please see license.txt


/* ==============================================
 * Agregar botones.
 * =========================================== */
function add_authorize_button(frm) {
	if (frm.doc.__islocal) {
		return;
	}
	frm.add_custom_button("Autorizar", function () {
		frappe.call({
			method: "frappe.integrations.doctype.mercadopago_settings.mercadopago_settings.get_auth_url_whitelisted",
			args: {
				account_name: frm.doc.account_name,
			},
			callback: function (response) {
				if (response.message.success) {
					window.location.href = response.message.result;
				} else {
					frappe.msgprint(response.message.result);
				}
			},
		});
	});
}

frappe.ui.form.on('Mercadopago Settings', {
	refresh: function (frm) {
		add_authorize_button(frm);
	},
});
