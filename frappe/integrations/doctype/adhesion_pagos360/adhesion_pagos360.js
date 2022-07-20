// Copyright (c) 2021, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Adhesion Pagos360", {
    refresh: function(frm) {
        if (!frm.doc.__islocal) {
            set_readonly_all_fields(frm);
        }

        if (frm.doc.estado != "canceled") {
            frm.add_custom_button("Cancelar", function() {
                frappe.confirm('¿Está seguro de que desea cancelar la adhesión?', function() {
                    frappe.call({
                        method: "erpnext_argentina.pagos360.cancelar_adhesion",
                        args: { adhesion: frm.doc.name },
                        callback: function(r) {
                            if (r.message) {
                                frappe.msgprint(r.message);
                                frm.refresh();
                            }
                        }
                    });
                });
            });
        }
    },
});

function set_readonly_all_fields(frm) {
    for (var i = 0; i < frm.fields.length; i++) {
        frm.set_df_property(frm.fields[i].df.fieldname, "read_only", 1);
    }
}
