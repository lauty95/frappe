"""utilities to generate a document name based on various rules defined.

NOTE:
From Version 14, The naming pattern is changed in a way that amended documents will
have the original name `orig_name` instead of `orig_name-X`. To make this happen
the cancelled document naming pattern is changed to 'orig_name-CANC-X'.

In version 13, whenever a submittable document is amended it's name is set to orig_name-X,
where X is a counter and it increments when amended again and so on. We are backporting
the version-14 styled naming into version-13 and will be available through system settings.
"""

# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import now_datetime, cint, cstr
import re
from six import string_types
from frappe.model import log_types


def set_new_name(doc, set_draft_name=False):
	"""
	Sets the `name` property for the document based on various rules.

	1. If amended doc, set suffix.
	2. If `autoname` method is declared, then call it.
	3. If `autoname` property is set in the DocType (`meta`), then build it using the `autoname` property.
	4. If no rule defined, use hash.

	:param doc: Document to be named.
	"""

	doc.run_method("before_naming")

	if set_draft_name:
		doc.name = "({0})".format(make_autoname('hash', doc.doctype))
		return

	autoname = frappe.get_meta(doc.doctype).autoname or ""

	if autoname.lower() != "prompt" and not frappe.flags.in_import:
		doc.name = None

	if getattr(doc, "amended_from", None):
		doc.name = _get_amended_name(doc)
		return

	elif getattr(doc.meta, "issingle", False):
		doc.name = doc.doctype

	elif getattr(doc.meta, "istable", False):
		doc.name = make_autoname("hash", doc.doctype)

	if not doc.name:
		set_naming_from_document_naming_rule(doc)

	if not doc.name:
		doc.run_method("autoname")

	if not doc.name and autoname:
		set_name_from_naming_options(autoname, doc)

	# if the autoname option is 'field:' and no name was derived, we need to
	# notify
	if not doc.name and autoname.startswith("field:"):
		fieldname = autoname[6:]
		frappe.throw(_("{0} is required").format(doc.meta.get_label(fieldname)))

	# at this point, we fall back to name generation with the hash option
	if not doc.name and autoname == "hash":
		doc.name = make_autoname("hash", doc.doctype)

	if not doc.name:
		doc.name = make_autoname("hash", doc.doctype)

	doc.name = validate_name(
		doc.doctype,
		doc.name,
		frappe.get_meta(doc.doctype).get_field("name_case")
	)

def set_name_from_naming_options(autoname, doc):
	"""
	Get a name based on the autoname field option
	"""

	_autoname = autoname.lower()

	if _autoname.startswith("field:"):
		doc.name = _field_autoname(autoname, doc)
	elif _autoname.startswith("naming_series:"):
		set_name_by_naming_series(doc)
	elif _autoname.startswith("prompt"):
		_prompt_autoname(autoname, doc)
	elif _autoname.startswith("format:"):
		doc.name = _format_autoname(autoname, doc)
	elif "#" in autoname:
		doc.name = make_autoname(autoname, doc=doc)

def set_naming_from_document_naming_rule(doc):
	'''
	Evaluate rules based on "Document Naming Series" doctype
	'''
	if doc.doctype in log_types:
		return

	# ignore_ddl if naming is not yet bootstrapped
	for d in frappe.get_all('Document Naming Rule',
		dict(document_type=doc.doctype, disabled=0), order_by='priority desc', ignore_ddl=True):
		frappe.get_cached_doc('Document Naming Rule', d.name).apply(doc)
		if doc.name:
			break

def set_name_by_naming_series(doc):
	"""Sets name by the `naming_series` property"""
	if not doc.naming_series:
		doc.naming_series = get_default_naming_series(doc.doctype)

	if not doc.naming_series:
		frappe.throw(frappe._("Naming Series mandatory"))

	doc.name = make_autoname(doc.naming_series+".#####", "", doc)

def make_autoname(key="", doctype="", doc=""):
	"""
	Creates an autoname from the given key:

	**Autoname rules:**

		 * The key is separated by '.'
		 * '####' represents a series. The string before this part becomes the prefix:
			Example: ABC.#### creates a series ABC0001, ABC0002 etc
		 * 'MM' represents the current month
		 * 'YY' and 'YYYY' represent the current year


   *Example:*

		 * DE/./.YY./.MM./.##### will create a series like
		   DE/09/01/0001 where 09 is the year, 01 is the month and 0001 is the series
	"""
	if key == "hash":
		return frappe.generate_hash(doctype, 10)

	if "#" not in key:
		key = key + ".#####"
	elif "." not in key:
		error_message = _("Invalid naming series (. missing)")
		if doctype:
			error_message = _("Invalid naming series (. missing) for {0}").format(doctype)

		frappe.throw(error_message)

	parts = key.split('.')
	n = parse_naming_series(parts, doctype, doc)
	return n


def parse_naming_series(parts, doctype='', doc=''):
	n = ''
	if isinstance(parts, string_types):
		parts = parts.split('.')
	series_set = False
	today = now_datetime()
	for e in parts:
		part = ''
		if e.startswith('#'):
			if not series_set:
				digits = len(e)
				part = getseries(n, digits)
				series_set = True
		elif e == 'YY':
			part = today.strftime('%y')
		elif e == 'MM':
			part = today.strftime('%m')
		elif e == 'DD':
			part = today.strftime("%d")
		elif e == 'YYYY':
			part = today.strftime('%Y')
		elif e == 'timestamp':
			part = str(today)
		elif e == 'FY':
			part = frappe.defaults.get_user_default("fiscal_year")
		elif e.startswith('{') and doc:
			e = e.replace('{', '').replace('}', '')
			part = doc.get(e)
		elif doc and doc.get(e):
			part = doc.get(e)
		else:
			part = e

		if isinstance(part, string_types):
			n += part

	return n


def getseries(key, digits):
	# series created ?
	current = frappe.db.sql("SELECT `current` FROM `tabSeries` WHERE `name`=%s FOR UPDATE", (key,))
	if current and current[0][0] is not None:
		current = current[0][0]
		# yes, update it
		frappe.db.sql("UPDATE `tabSeries` SET `current` = `current` + 1 WHERE `name`=%s", (key,))
		current = cint(current) + 1
	else:
		# no, create it
		frappe.db.sql("INSERT INTO `tabSeries` (`name`, `current`) VALUES (%s, 1)", (key,))
		current = 1
	return ('%0'+str(digits)+'d') % current


def revert_series_if_last(key, name, doc=None):
	if frappe.get_system_settings('use_original_name_for_amended_document',
			ignore_if_not_exists=True) and hasattr(doc, 'amended_from'):
		# Do not revert the series if the document is amended.
		if doc.amended_from:
			return

		# Get document name by parsing incase of fist cancelled document
		if doc.docstatus == 2 and not doc.amended_from:
			if doc.name.endswith('-CANC'):
				name, _ = NameParser.parse_docname(doc.name, sep='-CANC')
			else:
				name, _ = NameParser.parse_docname(doc.name, sep='-CANC-')

	if ".#" in key:
		prefix, hashes = key.rsplit(".", 1)
		if "#" not in hashes:
			return
	else:
		prefix = key

	if '.' in prefix:
		prefix = parse_naming_series(prefix.split('.'), doc=doc)

	count = cint(name.replace(prefix, ""))
	current = frappe.db.sql("SELECT `current` FROM `tabSeries` WHERE `name`=%s FOR UPDATE", (prefix,))

	if current and current[0][0]==count:
		frappe.db.sql("UPDATE `tabSeries` SET `current` = `current` - 1 WHERE `name`=%s", prefix)


def get_default_naming_series(doctype):
	"""get default value for `naming_series` property"""
	naming_series = frappe.get_meta(doctype).get_field("naming_series").options or ""
	if naming_series:
		naming_series = naming_series.split("\n")
		return naming_series[0] or naming_series[1]
	else:
		return None


def validate_name(doctype, name, case=None, merge=False):
	if not name:
		frappe.throw(_("No Name Specified for {0}").format(doctype))
	if name.startswith("New "+doctype):
		frappe.throw(_("There were some errors setting the name, please contact the administrator"), frappe.NameError)
	if case == "Title Case":
		name = name.title()
	if case == "UPPER CASE":
		name = name.upper()
	name = name.strip()

	if not frappe.get_meta(doctype).get("issingle") and (doctype == name) and (name != "DocType"):
		frappe.throw(_("Name of {0} cannot be {1}").format(doctype, name), frappe.NameError)

	special_characters = "<>"
	if re.findall("[{0}]+".format(special_characters), name):
		message = ", ".join("'{0}'".format(c) for c in special_characters)
		frappe.throw(_("Name cannot contain special characters like {0}").format(message), frappe.NameError)

	return name


def append_number_if_name_exists(doctype, value, fieldname="name", separator="-", filters=None):
	if not filters:
		filters = dict()
	filters.update({fieldname: value})
	exists = frappe.db.exists(doctype, filters)

	regex = "^{value}{separator}\\d+$".format(value=re.escape(value), separator=separator)

	if exists:
		last = frappe.db.sql("""SELECT `{fieldname}` FROM `tab{doctype}`
			WHERE `{fieldname}` {regex_character} %s
			ORDER BY length({fieldname}) DESC,
			`{fieldname}` DESC LIMIT 1""".format(
				doctype=doctype,
				fieldname=fieldname,
				regex_character=frappe.db.REGEX_CHARACTER),
			regex)

		if last:
			count = str(cint(last[0][0].rsplit(separator, 1)[1]) + 1)
		else:
			count = "1"

		value = "{0}{1}{2}".format(value, separator, count)

	return value


def _get_amended_name(doc):
	if frappe.get_system_settings('use_original_name_for_amended_document', ignore_if_not_exists=True):
		name, _ = NameParser(doc).parse_amended_from()
	else:
		am_id = 1
		am_prefix = doc.amended_from
		if frappe.db.get_value(doc.doctype, doc.amended_from, "amended_from"):
			am_id = cint(doc.amended_from.split("-")[-1]) + 1
			am_prefix = "-".join(doc.amended_from.split("-")[:-1])  # except the last hyphen

		name = am_prefix + "-" + str(am_id)
	return name

def _field_autoname(autoname, doc, skip_slicing=None):
	"""
	Generate a name using `DocType` field. This is called when the doctype's
	`autoname` field starts with 'field:'
	"""
	fieldname = autoname if skip_slicing else autoname[6:]
	name = (cstr(doc.get(fieldname)) or "").strip()
	return name

def _prompt_autoname(autoname, doc):
	"""
	Generate a name using Prompt option. This simply means the user will have to set the name manually.
	This is called when the doctype's `autoname` field starts with 'prompt'.
	"""
	# set from __newname in save.py
	if not doc.name:
		frappe.throw(_("Name not set via prompt"))

def _format_autoname(autoname, doc):
	"""
	Generate autoname by replacing all instances of braced params (fields, date params ('DD', 'MM', 'YY'), series)
	Independent of remaining string or separators.

	Example pattern: 'format:LOG-{MM}-{fieldname1}-{fieldname2}-{#####}'
	"""

	first_colon_index = autoname.find(":")
	autoname_value = autoname[first_colon_index + 1:]

	def get_param_value_for_match(match):
		param = match.group()
		# trim braces
		trimmed_param = param[1:-1]
		return parse_naming_series([trimmed_param], doc=doc)

	# Replace braced params with their parsed value
	name = re.sub(r"(\{[\w | #]+\})", get_param_value_for_match, autoname_value)

	return name

class NameParser:
	"""Parse document name and return parts of it.

	NOTE: It handles cancellend and amended doc parsing for now. It can be expanded.
	"""
	def __init__(self, doc):
		self.doc = doc

	def parse_amended_from(self):
		"""
		Cancelled document naming will be in one of these formats

		* original_name-X-CANC - This is introduced to migrate old style naming to new style
		* original_name-CANC - This is introduced to migrate old style naming to new style
		* original_name-CANC-X - This is the new style naming

		New style naming: In new style naming amended documents will have original name. That says,
		when a document gets cancelled we need rename the document by adding `-CANC-X` to the end
		so that amended documents can use the original name.

		Old style naming: cancelled documents stay with original name and when amended, amended one
		gets a new name as `original_name-X`. To bring new style naming we had to change the existing
		cancelled document names and that is done by adding `-CANC` to cancelled documents through patch.
		"""
		if not getattr(self.doc, 'amended_from', None):
			return (None, None)

		# Handle old style cancelled documents (original_name-X-CANC, original_name-CANC)
		if self.doc.amended_from.endswith('-CANC'):
			name, _ = self.parse_docname(self.doc.amended_from, '-CANC')

			# Handle format original_name-X-CANC.
			if frappe.db.get_value(self.doc.doctype, self.doc.amended_from, "amended_from"):
				return self.parse_docname(name, '-')
			return name, None

		# Handle new style cancelled documents
		return self.parse_docname(self.doc.amended_from, '-CANC-')

	@classmethod
	def parse_docname(cls, name, sep='-'):
		split_list = name.rsplit(sep, 1)

		if len(split_list) == 1:
			return (name, None)
		return (split_list[0], split_list[1])

def get_cancelled_doc_latest_counter(tname, docname):
	"""Get the latest counter used for cancelled docs of given docname.
	"""
	name_prefix = f'{docname}-CANC-'

	rows = frappe.db.sql("""
		select
			name
		from `tab{tname}`
		where
			name like %(name_prefix)s and docstatus=2
	""".format(tname=tname), {'name_prefix': name_prefix+'%'}, as_dict=1)

	if not rows:
		return -1
	return max([int(row.name.replace(name_prefix, '') or -1) for row in rows])

def gen_new_name_for_cancelled_doc(doc):
	"""Generate a new name for cancelled document.
	"""
	if getattr(doc, "amended_from", None):
		name, _ = NameParser(doc).parse_amended_from()
	else:
		name = doc.name

	counter = get_cancelled_doc_latest_counter(doc.doctype, name)
	return f'{name}-CANC-{counter+1}'
