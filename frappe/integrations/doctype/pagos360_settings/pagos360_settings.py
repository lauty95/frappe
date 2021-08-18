# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

from json.encoder import JSONEncoder
import datetime
import requests
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.integrations.utils import create_request_log, make_get_request, create_payment_gateway
from frappe.utils import call_hook_method


class Pagos360Settings(Document):

    supported_currencies = ["ARS"]

    def validate_transaction_currency(self, currency):
        if currency not in self.supported_currencies:
            frappe.throw(_("Please select another payment method. Pagos360 does not support transactions in currency '{0}'").format(currency))

    def validate(self):
        create_payment_gateway("Pagos360")
        call_hook_method('payment_gateway_enabled', gateway="Pagos360")
        if not self.flags.ignore_mandatory:
            self.validate_pagos360_credentails()

    def validate_pagos360_credentails(self):
        try:
            make_get_request("https://api.pagos360.com/account", headers={'authorization': 'Bearer ' + self.api_key})
        except Exception:
            frappe.throw(_("Invalid payment gateway credentials"))


class Pagos360:

    base_url = 'https://api.pagos360.com/'
    mime_type = 'application/json'

    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {'authorization': 'Bearer ' + self.api_key, 'Content-type': self.mime_type}

    def get(self, uri, params=None):
        api_result = requests.get(self.base_url + uri, params=params, headers=self.headers)
        return {"status": api_result.status_code, "response": api_result.json()}

    def post(self, uri, data=None, params=None):
        if data is not None:
            data = JSONEncoder().encode(data)

        api_result = requests.post(self.base_url + uri, params=params, data=data, headers=self.headers)

        return {"status": api_result.status_code, "response": api_result.json()}

    def put(self, uri, data=None, params=None):
        if data is not None:
            data = JSONEncoder().encode(data)

        api_result = self.put(self.base_url + uri, params=params, data=data, headers=self.headers)

        return {"status": api_result.status_code, "response": api_result.json()}

    def validate_date(self, date=None):
        if not date:
            return (datetime.datetime.today() - datetime.timedelta(days=1)).strftime("%d-%m-%Y")
        if type(date) != str:
            return date.strftime("%d-%m-%Y")
        return date

    def get_account_balance(self):
        return self.get("account/balances/")

    def get_collection_report(self, date=None):
        return self.get("report/collection/" + self.validate_date(date))

    def get_chargeback_report(self, date=None):
        return self.get("report/chargeback/" + self.validate_date(date))

    def get_settlement_report(self, date=None):
        return self.get("report/settlement/" + self.validate_date(date))

    def get_card_adhesion(self, id):
        return self.get("card-adhesion/" + str(id))

    def create_card_adhesion(self, data):
        return self.post("card-adhesion/", data)

    def cancel_card_adhesion(self, id):
        return self.put("card-adhesion/{}/cancel".format(id))

    def get_cbu_adhesion(self, id):
        return self.get("adhesion/" + str(id))

    def create_cbu_adhesion(self, data):
        return self.post("adhesion/", data)

    def cancel_cbu_adhesion(self, id):
        return self.put("adhesion/{}/cancel".format(id))

    def create_card_debit_request(self, data):
        return self.post("card-debit-request/", data)

    def get_card_debit_request(self, id):
        return self.get("card-debit-request/" + str(id))

    def cancel_card_debit_request(self, id):
        return self.get("card-debit-request/{}/cancel/".format(id))

    def create_cbu_debit_request(self, data):
        return self.post("debit-request/", data)

    def get_cbu_debit_request(self, id):
        return self.get("debit-request/" + str(id))

    def cancel_cbu_debit_request(self, id):
        return self.get("debit-request/{}/cancel/".format(id))

    def create_payment_request(self, data):
        return self.post("payment-request/", data)

    def get_payment_request(self, id):
        return self.get("payment-request/" + str(id))

    def get_next_business_day(self, data):
        if "next_business_day" not in data:
            data = {"next_business_day": data}
        return self.post("validator/next-business-day/", data)
