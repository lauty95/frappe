// Copyright (c) 2021, Diamo and contributors
// For license information, please see license.txt

frappe.listview_settings['Adhesion Pagos360'] = {
	add_fields: ["estado"],
	get_indicator: function(doc) {
		var color = {
			'signed': 'green',
			'pending_to_sign': 'darkgrey',
			'canceled': 'red'
		}
		return [doc.estado, color[doc.estado], "estado,=," + doc.estado];	
	}
};
