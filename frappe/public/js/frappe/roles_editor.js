frappe.RoleEditor = class {
	constructor(wrapper, frm, disable) {
		this.frm = frm;
		this.wrapper = wrapper;
		this.disable = disable;
		let user_roles = this.frm.doc.roles.map(a => a.role);
		this.multicheck = frappe.ui.form.make_control({
			parent: wrapper,
			df: {
				fieldname: "roles",
				fieldtype: "MultiCheck",
				select_all: true,
				columns: 3,
				get_data: () => {
					return frappe.xcall('frappe.core.doctype.user.user.get_all_roles').then(roles => {
						return roles.map(role => {
							return {
								label: __(role),
								value: role,
								checked: user_roles.includes(role)
							};
						});
					});
				},
				on_change: () => {
					this.set_roles_in_table();
					this.frm.dirty();
				}
			},
			render_input: true
		});

		let original_func = this.multicheck.make_checkboxes;
		this.multicheck.make_checkboxes = () => {
			original_func.call(this.multicheck);
			this.multicheck.$wrapper.find('.label-area').click(e => {
				let role = $(e.target).data('unit');
				role && this.show_permissions(role);
				e.preventDefault();
			});
		};
	}
	set_enable_disable() {
		$(this.wrapper).find('input[type="checkbox"]').attr('disabled', this.disable ? true : false);
	}
	show_permissions(role) {
		// show permissions for a role
		if (!this.perm_dialog) {
			this.make_perm_dialog();
		}
		$(this.perm_dialog.body).empty();
		return frappe.xcall('frappe.core.doctype.user.user.get_perm_info', { role })
			.then(permissions => {
				const $body = $(this.perm_dialog.body);
				if (!permissions.length) {
					$body.append(`<div class="text-muted text-center padding">
						${__('{0} role does not have permission on any doctype', [role])}
					</div>`);
				} else {
					var p_th = ''
					// __('Write') __('Read') __('Share')
					for (const p of frappe.perm.rights) { 
						if (p == 'write') {
							p_th += '<th> Leer</th>'
						} else if (p == 'read') {
							p_th += '<th> Escribir</th>'
						} else if (p == 'share') {
							p_th += '<th> Compartir</th>'
						} else {
							p_th += '<th> ' + __(frappe.unscrub(p)) + '</th>'
						}
					}
					$body.append(`
						<table class="user-perm">
							<thead>
								<tr>
									<th> ${__('Document Type')} </th>
									<th> ${__('Level')} </th>
									${p_th}
								</tr>
							</thead>
							<tbody></tbody>
						</table>
					`);
					permissions.forEach(perm => {
						$body.find('tbody').append(`
							<tr>
								<td>${__(perm.parent)}</td>
								<td>${__(perm.permlevel)}</td>
								${frappe.perm.rights.map(p => `<td class="text-muted bold">${perm[p] ? frappe.utils.icon('check', 'xs') : '-'}</td>`).join("")}
							</tr>
						`);
					});
				}
				this.perm_dialog.set_title(__(role));
				this.perm_dialog.show();
			});
	}
	make_perm_dialog() {
		this.perm_dialog = new frappe.ui.Dialog({
			title: __('Role Permissions')
		});

		this.perm_dialog.$wrapper
			.find('.modal-dialog')
			.css("width", "1200px")
			.css("max-width", "80vw");
	}
	show() {
		let user_roles = this.frm.doc.roles.map(a => a.role);
		this.multicheck.selected_options = user_roles;
		this.multicheck.refresh_input();
		this.set_enable_disable();
	}
	set_roles_in_table() {
		let roles = this.frm.doc.roles || [];
		let checked_options = this.multicheck.get_checked_options();
		roles.map(role_doc => {
			if (!checked_options.includes(role_doc.role)) {
				frappe.model.clear_doc(role_doc.doctype, role_doc.name);
			}
		});
		checked_options.map(role => {
			if (!roles.find(d => d.role === role)) {
				let role_doc = frappe.model.add_child(this.frm.doc, "Has Role", "roles");
				role_doc.role = role;
			}
		});
	}
	get_roles() {
		return {
			checked_roles: this.multicheck.get_checked_options(),
			unchecked_roles: this.multicheck.get_unchecked_options()
		};
	}
};