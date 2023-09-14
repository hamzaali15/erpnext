import copy
import json
from frappe.model.document import Document
import frappe
import csv
from erpnext.controllers.item_variant import create_variant
from frappe.utils import (
	add_days,
	add_months,
	cint,
	date_diff,
	flt,
	get_datetime,
	get_last_day,
	getdate,
	month_diff,
	nowdate,
	today,
)
import requests
from frappe import _
#ss

class PurchaseOrderImport(Document):
	def after_insert(self):
		frappe.enqueue('erpnext.erpnext_integrations.connectors.woocommerce_connection.long_job', self=self,now=True,at_front=True, queue="long",timeout=9000)
