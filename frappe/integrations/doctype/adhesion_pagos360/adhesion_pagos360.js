// Copyright (c) 2021, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Adhesion Pagos360", {
    refresh: function(frm) {
        if (!frm.doc.__islocal) {
            set_readonly_all_fields(frm);
        }

        frm.add_custom_button('Enviar link de adhesión', function() {
            frappe.call({
                method: "erpnext_argentina.facturacion.enviar_adhesion",
                args: { subscription: frm.doc.key, is_key: true},
                callback: function(r, rt) {
                    if (r.message) { 
                        frappe.msgprint({indicator: 'green', message: r.message,});
                    }
                }
            });
        });
	
        frm.add_custom_button('Ir a la Suscripción', function() {
            frappe.call({
                method: "erpnext_argentina.facturacion.get_subscription_name_from_key",
                args: { key: frm.doc.key },
                callback: function(r, rt) {
                    if (r.message) { 
                        frappe.set_route('Form', "Subscription", r.message);
                    }
                }
            });
        });
    },
});

function set_readonly_all_fields(frm) {
    for (var i = 0; i < frm.fields.length; i++) {
        frm.set_df_property(frm.fields[i].df.fieldname, "read_only", 1);
    }
}
