frappe.pages['informacion-de-uso'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Información de Uso',
		single_column: true
	});

	frappe.call({
		method: "frappe.limits.get_usage_info",
		callback: function(r) {
			var usage_info = r.message;
			if (!usage_info) {
				return;
			}

			let limits = usage_info.limits;
			let database_percent = (limits.space_usage.database_size / limits.space) * 100;
			let files_percent = (limits.space_usage.files_size / limits.space) * 100;
			let backup_percent = (limits.space_usage.backup_size / limits.space) * 100;

			let total_consumed = database_percent + files_percent + backup_percent;

			let last_part = backup_percent;
			if (total_consumed > 100) {
				last_part = backup_percent - (total_consumed - 100);
			}
			backup_percent = last_part;

			let usage_message = '';
			if (limits.space_usage.total > limits.space) {
				usage_message = __('Ha utilizado todo el espacio que se le ha asignado. Por favor, compre más espacio en su suscripción.');
			} else {
				let available = flt(limits.space - limits.space_usage.total, 2);
				usage_message = __('{0} disponible de {1}', [(available + ' MB').bold(), (limits.space + ' MB').bold()]);
			}

			$(frappe.render_template("informacion_de_uso", Object.assign(usage_info, {
				database_percent,
				files_percent,
				backup_percent,
				usage_message
			}))).appendTo(page.main);

			var btn_text = usage_info.limits.users == 1 ? __("Ampliar") : __("Renovar / Ampliar");
			$(page.main).find('.btn-primary').html(btn_text).on('click', () => {
				window.open(usage_info.upgrade_url);
			});
		}
	});

}