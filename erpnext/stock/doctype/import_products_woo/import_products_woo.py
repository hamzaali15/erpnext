
import copy
import json
from frappe.model.document import Document
import frappe
import csv
from frappe import _
from erpnext.controllers.item_variant import create_variant
from frappe.utils import (
	add_days,
	nowdate,
)
import requests
from frappe.model.document import Document

class ImportProductsWoo(Document):
	def after_insert(self):
			indexDescription = '' #('/Users/macbookpro/frappe/erpnext/frappe-bench/sites/erpnext.local/'+self.import_file, "r")('/cloudclusters/erpnext/frappe-bench/sites/default/'+self.import_file, "r") 
			with open('/cloudclusters/erpnext/frappe-bench/sites/default/'+self.import_file, "r") as file:
			    csvreader = csv.reader(file)
			    next(csvreader)
			    for row in csvreader:
			        if  frappe.db.exists("Item",{'item_code':row[1]}):
			            item = frappe.get_doc("Item", {'item_code':row[1]})
			            item.cost = row[2]
			            item.save()