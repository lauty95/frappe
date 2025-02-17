frappe.email_defaults = {
	"GMail": {
		"email_server": "imap.gmail.com",
		"use_ssl": 1,
		"enable_outgoing": 1,
		"smtp_server": "smtp.gmail.com",
		"smtp_port": 587,
		"use_tls": 1,
		"use_imap": 1
	},
	"Outlook.com": {
		"email_server": "imap-mail.outlook.com",
		"use_ssl": 1,
		"enable_outgoing": 1,
		"smtp_server": "smtp-mail.outlook.com",
		"smtp_port": 587,
		"use_tls": 1,
		"use_imap": 1
	},
	"Sendgrid": {
		"enable_outgoing": 1,
		"smtp_server": "smtp.sendgrid.net",
		"smtp_port": 587,
		"use_tls": 1,
	},
	"SparkPost": {
		"enable_incoming": 0,
		"enable_outgoing": 1,
		"smtp_server": "smtp.sparkpostmail.com",
		"smtp_port": 587,
		"use_tls": 1
	},
	"Yahoo Mail": {
		"email_server": "imap.mail.yahoo.com",
		"use_ssl": 1,
		"enable_outgoing": 1,
		"smtp_server": "smtp.mail.yahoo.com",
		"smtp_port": 587,
		"use_tls": 1,
		"use_imap": 1
	},
	"Yandex.Mail": {
		"email_server": "imap.yandex.com",
		"use_ssl": 1,
		"enable_outgoing": 1,
		"smtp_server": "smtp.yandex.com",
		"smtp_port": 587,
		"use_tls": 1,
		"use_imap": 1
	},
};

frappe.email_defaults_pop = {
	"GMail": {
		"email_server": "pop.gmail.com"
	},
	"Outlook.com": {
		"email_server": "pop3-mail.outlook.com"
	},
	"Yahoo Mail": {
		"email_server": "pop.mail.yahoo.com"
	},
	"Yandex.Mail": {
		"email_server": "pop.yandex.com"
	},

};

frappe.ui.form.on("Email Account", {
	service: function(frm) {
		$.each(frappe.email_defaults[frm.doc.service], function(key, value) {
			frm.set_value(key, value);
		});
		if (!frm.doc.use_imap) {
			$.each(frappe.email_defaults_pop[frm.doc.service], function(key, value) {
				frm.set_value(key, value);
			});
		}
		frm.events.show_gmail_message_for_less_secure_apps(frm);
	},

	use_imap: function(frm) {
		if (!frm.doc.use_imap) {
			$.each(frappe.email_defaults_pop[frm.doc.service], function(key, value) {
				frm.set_value(key, value);
			});
		}
		else{
			$.each(frappe.email_defaults[frm.doc.service], function(key, value) {
				frm.set_value(key, value);
			});
		}
	},

	enable_incoming: function(frm) {
		frm.doc.no_remaining = null; //perform full sync
		//frm.set_df_property("append_to", "reqd", frm.doc.enable_incoming);
		frm.trigger("warn_autoreply_on_incoming");
	},

	enable_auto_reply: function(frm) {
		frm.trigger("warn_autoreply_on_incoming");
	},

	notify_if_unreplied: function(frm) {
		frm.set_df_property("send_notification_to", "reqd", frm.doc.notify_if_unreplied);
	},

	onload: function(frm) {
		frm.set_df_property("append_to", "only_select", true);
		frm.set_query("append_to", "frappe.email.doctype.email_account.email_account.get_append_to");
	},

	refresh: function(frm) {
		frm.events.set_domain_fields(frm);
		frm.events.enable_incoming(frm);
		frm.events.notify_if_unreplied(frm);
		frm.events.show_gmail_message_for_less_secure_apps(frm);

		if(frappe.route_flags.delete_user_from_locals && frappe.route_flags.linked_user) {
			delete frappe.route_flags.delete_user_from_locals;
			delete locals['User'][frappe.route_flags.linked_user];
		}
	},

	show_gmail_message_for_less_secure_apps: function(frm) {
		frm.dashboard.clear_headline();
		if(frm.doc.service==="GMail") {
			frm.dashboard.set_headline_alert('Gmail sólo funcionará si permites el acceso a aplicaciones menos seguras en la configuración de Gmail. <a target="_blank" href="https://support.google.com/accounts/answer/6010255?hl=en">Lee esto para más detalles</a>');
		}
	},

	email_id:function(frm) {
		//pull domain and if no matching domain go create one
		frm.events.update_domain(frm);
	},

	update_domain: function(frm){
		if (!frm.doc.email_id && !frm.doc.service){
			return;
		}

		frappe.call({
			method: 'get_domain',
			doc: frm.doc,
			args: {
				"email_id": frm.doc.email_id
			},
			callback: function (r) {
				if (r.message) {
					frm.events.set_domain_fields(frm, r.message);
				}
			}
		});
	},

	set_domain_fields: function(frm, args) {
		if(!args){
			args = frappe.route_flags.set_domain_values? frappe.route_options: {};
		}

		for(var field in args) {
			frm.set_value(field, args[field]);
		}

		delete frappe.route_flags.set_domain_values;
		frappe.route_options = {};
	},

	email_sync_option: function(frm) {
		// confirm if the ALL sync option is selected

		if(frm.doc.email_sync_option == "ALL"){
			var msg = __("You are selecting Sync Option as ALL, It will resync all \
				read as well as unread message from server. This may also cause the duplication\
				of Communication (emails).");
			frappe.confirm(msg, null, function() {
				frm.set_value("email_sync_option", "UNSEEN");
			});
		}
	},

	warn_autoreply_on_incoming: function(frm) {
		if (frm.doc.enable_incoming && frm.doc.enable_auto_reply && frm.doc.__islocal) {
			var msg = __("Enabling auto reply on an incoming email account will send automated replies \
				to all the synchronized emails. Do you wish to continue?");
			frappe.confirm(msg, null, function() {
				frm.set_value("enable_auto_reply", 0);
				frappe.show_alert({message: __("Disabled Auto Reply"), indicator: "blue"});
			});
		}
	}
});
