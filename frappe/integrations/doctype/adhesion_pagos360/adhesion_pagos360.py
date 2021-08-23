# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

import base64
import frappe
import erpnext
from frappe.model.document import Document
from frappe.integrations.doctype.pagos360_settings.pagos360_settings import Pagos360
from frappe.integrations.utils import get_payment_gateway_controller
from frappe.utils import validate_email_address


class AdhesionPagos360(Document):

    def validate(self):
        if not self.key:
            frappe.throw("Hubo un error, vuelva a intentarlo ingresando al link nuevamente")

        validate_email_address(self.email, True)
        self.validate_cuit_cuil()
        self.validate_cbu()

    def validate_cuit_cuil(self):
        if self.cbu_holder_id_number and len(self.cbu_holder_id_number) != 11:
            frappe.throw("CUIT/CUIL del titular de la cuenta inválido")

    def validate_cbu(self):
        """Checks to see if the value provided is a valid CBU."""
        if not self.cbu_number:
            return

        def calc_check_digit(value):
            """Calculate the check digit."""
            weights = (3, 1, 7, 9)
            check = sum(int(n) * weights[i % 4]
                        for i, n in enumerate(reversed(value)))
            return str((10 - check) % 10)

        if not self.cbu_number.isdigit():
            frappe.throw("CBU inválido, sólo se permiten números.")
        if len(self.cbu_number) != 22:
            frappe.throw("CBU inválido, debe contener 22 números.")
        if calc_check_digit(self.cbu_number[:7]) != self.cbu_number[7]:
            frappe.throw("CBU inválido.")
        if calc_check_digit(self.cbu_number[8:-1]) != self.cbu_number[-1]:
            frappe.throw("CBU inválido.")

    def after_insert(self):
        if "erpnext" not in frappe.get_installed_apps():
            frappe.throw("Debe tener instalado DiamoERP para utilizar Adhesion de Pagos360")

        keydeco = base64.b64decode(self.key).decode("utf-8", "ignore")

        if not frappe.db.exists("Subscription", keydeco):
            return

        subscription = frappe.get_doc("Subscription", keydeco)

        if not subscription.adhesion_pagos360:
            subscription.adhesion_pagos360 = self.name
            subscription.save(ignore_permissions=True)
            frappe.db.commit()

            if subscription.status not in ["Cancelled", "Trialling"]:
                self.crear(subscription)

    def crear(self, subscription):
        from erpnext_argentina.facturacion import pago360_log_error

        pagos360_settings = get_payment_gateway_controller("Pagos360")
        pago360 = Pagos360(pagos360_settings.get_password("api_key"), sandbox=pagos360_settings.sandbox)

        company = erpnext.get_default_company(frappe.session.user) or ""

        # adhesion_holder_name    String  SI  Nombre del titular del servicio que se debitará (hasta 50 caracteres).
        adhesion = {"adhesion_holder_name": self.adhesion_holder_name}

        # email   String  SI  Email del titular de la tarjeta (hasta 255 caracteres).
        adhesion.update({"email": self.email})

        # description String  SI  Descripción o concepto de la Adhesión (hasta 255 caracteres).
        adhesion.update({"description": "Suscripcion a {}".format(company)})

        # external_reference  String  SI  Este atributo se puede utilizar como referencia para identificar la Adhesión y sincronizar con tus sistemas de backend el origen de la operación. Algunos valores comúnmente utilizados son: ID de Cliente, DNI, CUIT, ID de venta o Nro. de Factura entre otros (hasta 255 caracteres).
        adhesion.update({"external_reference": subscription.name})

        # metadata Object  NO  Objeto JSON que se puede utilizar para guardar atributos adicionales en la adhesión y poder sincronizar con tus sistemas de backend. Pagos360.com no utiliza este objeto.
        adhesion.update({"metadata": {}})

        if self.tipo == "Crédito":
            nombre_objeto = "card_adhesion"

            # card_number String  SI  Hash en Base64 que contiene la Encriptación del Número de Tarjeta en la que se ejecutarán los débitos automáticos (hasta 19 caracteres).
            # Al parecer no es en Base64... 16 digitos maximo.
            adhesion.update({"card_number": self.card_number})

            # card_holder_name    String  SI  Nombre del titular de la Tarjeta (hasta 255 caracteres).
            adhesion.update({"card_holder_name": self.card_holder_name})

            method = pago360.create_card_adhesion

        elif self.tipo == "Débito":
            nombre_objeto = "adhesion"

            # short_description   String  SI  Descripción Bancaria que se mostrará en el resumen de la cuenta bancaria del pagador (hasta 10 caracteres).
            adhesion.update({"short_description": company[0:10]})

            # cbu_number  String  SI  Número de CBU de la cuenta bancaria en la que se ejecutarán los débitos (hasta 22 caracteres).
            adhesion.update({"cbu_number": self.cbu_number})

            # cbu_holder_id_number    Integer SI  CUIT/CUIL del títular de la cuenta bancaria.
            adhesion.update({"cbu_holder_id_number": int(self.cbu_holder_id_number.replace("-", "").replace(".", ""))})

            # cbu_holder_name String  SI  Nombre del titular de la cuenta bancaria (hasta 255 caracteres).
            adhesion.update({"cbu_holder_name": self.cbu_holder_name})

            method = pago360.create_cbu_adhesion

        data = {nombre_objeto: adhesion}

        result = method(data)

        if result.get("status", "") == 201:
            frappe.db.set_value('Adhesion Pagos360', self.name, 'id_adhesion', result.get("response", {}).get("id", ""))
            frappe.db.set_value('Adhesion Pagos360', self.name, 'estado', result.get("response", {}).get("state", "error"))
        else:
            pago360_log_error("Pagos360 devolvio {e}".format(e=result.get("status", "")), data=result, exception=True)
            frappe.throw("Pagos360 devolvio {e}".format(e=result.get("status", "")))
        frappe.db.commit()
