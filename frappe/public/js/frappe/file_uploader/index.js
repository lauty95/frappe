import FileUploaderComponent from './FileUploader.vue';

export default class FileUploader {
	constructor({
		wrapper,
		method,
		on_success,
		doctype,
		docname,
		fieldname,
		files,
		folder,
		restrictions,
		upload_notes,
		allow_multiple,
		as_dataurl,
		disable_file_browser,
		frm
	} = {}) {

		frm && frm.attachments.max_reached(true);

		if (!wrapper) {
			this.make_dialog();
		} else {
			this.wrapper = wrapper.get ? wrapper.get(0) : wrapper;
		}

		this.$fileuploader = new Vue({
			el: this.wrapper,
			render: h => h(FileUploaderComponent, {
				props: {
					show_upload_button: !Boolean(this.dialog),
					doctype,
					docname,
					fieldname,
					method,
					folder,
					on_success,
					restrictions,
					upload_notes,
					allow_multiple,
					as_dataurl,
					disable_file_browser,
				}
			})
		});

		this.uploader = this.$fileuploader.$children[0];

		this.uploader.$watch('files', (files) => {
			let all_private = files.every(file => file.private);
			if (this.dialog) {
				this.dialog.set_secondary_action_label(all_private ? __('Establecer todos publicos') : __('Establecer todos privados'));
			}
		}, { deep: true });

		if (files && files.length) {
			this.uploader.add_files(files);
		}
	}

	upload_files() {
		this.dialog && this.dialog.get_primary_btn().prop('disabled', true);
		return this.uploader.upload_files()
			.then(() => {
				this.dialog && this.dialog.hide();
			});
	}

	make_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __('Subir'),
			primary_action_label: __('Subir'),
			primary_action: () => this.upload_files(),
			secondary_action_label: __('Establecer todos privados'),
			secondary_action: () => {
				this.uploader.toggle_all_private();
			}
		});

		this.wrapper = this.dialog.body;
		this.dialog.show();
		this.dialog.$wrapper.on('hidden.bs.modal', function() {
			$(this).data('bs.modal', null);
			$(this).remove();
		});
	}
}
