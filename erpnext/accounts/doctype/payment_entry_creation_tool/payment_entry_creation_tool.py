# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import publish_progress
# from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.erpnext_integrations.connectors.woocommerce_connection import change_status
from frappe.utils import nowdate, today
import openpyxl
import requests
from io import BytesIO
from frappe.model.document import Document


class PaymentEntryCreationTool(Document):
	@frappe.whitelist()
	def create_payment_entries(self):
		if frappe.db.exists('File', {'file_url': self.sales_invoice_list}):
			file_doc = frappe.get_doc("File", {"file_url": self.sales_invoice_list})
			parts = file_doc.get_extension()
			extension = parts[1]

			if extension == '.xlsx':
				try:
					content = file_doc.get_content()
					workbook = openpyxl.load_workbook(BytesIO(content))
					sheet = workbook.active
					order_ids_list = [str(cell.value) for cell in sheet['A'][1:]]
				except Exception as e:
					frappe.msgprint(f"Error reading XLSX file: {str(e)}", 'Invalid File')
					return
			elif extension == '.csv':
				content = file_doc.get_content()
				order_ids_list = content.strip().split('\n')[1:]
			else:
				frappe.msgprint('The File extension should be CSV or XLSX type.', 'Invalid File')
				return
			frappe.msgprint("Payment Entry is Creating in the background")
			if len(order_ids_list) <= 10:
				create_payment_entries(self)
			else:
				frappe.enqueue(create_payment_entries, self=self, queue="long")
			
		else:
			frappe.msgprint('The File does not exist.', 'Invalid File')
			return

	# @frappe.whitelist()
	# def update_order_status_after_payment(self):
	# 	if frappe.db.exists('File', {'file_url': self.sales_invoice_list}):
	# 		file_doc = frappe.get_doc("File", {"file_url": self.sales_invoice_list})
	# 		parts = file_doc.get_extension()
	# 		extension = parts[1]
	# 		if extension == '.xlsx':
	# 			try:
	# 				content = file_doc.get_content()
	# 				workbook = openpyxl.load_workbook(BytesIO(content))
	# 				sheet = workbook.active
	# 				order_ids_list = [str(cell.value) for cell in sheet['A'][1:]]
	# 			except Exception as e:
	# 				frappe.msgprint(f"Error reading XLSX file: {str(e)}", 'Invalid File')
	# 				return
	# 		elif extension == '.csv':
	# 			content = file_doc.get_content()
	# 			order_ids_list = content.strip().split('\n')[1:]
	# 		else:
	# 			frappe.msgprint('The File extension should be CSV or XLSX type.', 'Invalid File')
	# 			return
	# 		frappe.msgprint("Sales Order status is updating in the background")
	# 		frappe.enqueue(update_order_status_after_payment, self=self, queue="long")
	# 		return "Success"
	# 	else:
	# 		frappe.msgprint('The File does not exist.', 'Invalid File')
	# 		return


def create_payment_entries(self):
	if frappe.db.exists('File', {'file_url': self.sales_invoice_list}):
		file_doc = frappe.get_doc("File", {"file_url": self.sales_invoice_list})
		parts = file_doc.get_extension()
		extension = parts[1]
		if extension == '.xlsx':
			try:
				content = file_doc.get_content()
				workbook = openpyxl.load_workbook(BytesIO(content))
				sheet = workbook.active
				order_ids_list = [str(cell.value) for cell in sheet['A'][1:]]
			except Exception as e:
				frappe.msgprint(f"Error reading XLSX file: {str(e)}", 'Invalid File')
				return
		elif extension == '.csv':
			content = file_doc.get_content()
			order_ids_list = content.strip().split('\n')
	for d in order_ids_list:
		if d and d != 'None':
			if frappe.db.exists("Sales Invoice", {"po_no": d, "docstatus": 1, "status": ["in", ["Unpaid", "Overdue"]]}):
				try:
					si = frappe.get_doc("Sales Invoice", {"po_no": d}).as_dict()
					# pe = get_payment_entry("Sales Invoice", si.name)
					# pe.po_no = d
					# pe.set_missing_values()

					# bank_account = pe.paid_to if pe.payment_type == "Receive" else pe.paid_from
					# bank_account_type = frappe.db.get_value("Account", bank_account, "account_type")
					# if bank_account_type == "Bank":
					# 	if not pe.reference_no or not pe.reference_date:
					# 		pe.reference_no = si.name
					# 		pe.reference_date = nowdate()

					# pe.insert(ignore_permissions=True)
					# pe.save(ignore_permissions=True)
					# pe.submit()
					# frappe.db.commit()

					# sales_order = frappe.get_doc("Sales Order", {"docstatus": 1, "woocommerce_id": d}).as_dict()
					pe = change_status([si], "payment_entry")

					#updating sales order status after payment entry creation
					# so = frappe.get_doc("Sales Order", {"docstatus": 1, "woocommerce_id": d})
					# so.woocommerce_status = "delivered"
					# so.status = "Delivered"
					# so.db_update()
					# frappe.db.commit()

					self.append("invoices_detail", {
						"order_id": d,
						"status": "Success",
						"description": "Payment Entry Created Successfully"
					})
					self.save()
					frappe.db.commit()
				except Exception as e:
					self.append("invoices_detail", {
						"order_id": d,
						"status": "Failed",
						"description": e  #"Payment Entry Creation Failed"
					})
					self.save()
					frappe.db.commit()
			else:
				self.append("invoices_detail", {
					"order_id": d,
					"status": "Failed",
					"description": "Sales Invoice is Paid/Cancelled or does not Exist"
				})
	# self.db_set('completed', 1)
	self.completed = 1
	self.save()
	frappe.db.commit()



# def update_order_status_after_payment(self):
# 	if frappe.db.exists('File', {'file_url': self.sales_invoice_list}):
# 		file_doc = frappe.get_doc("File", {"file_url": self.sales_invoice_list})
# 		parts = file_doc.get_extension()
# 		extension = parts[1]
# 		if extension == '.xlsx':
# 			try:
# 				content = file_doc.get_content()
# 				workbook = openpyxl.load_workbook(BytesIO(content))
# 				sheet = workbook.active
# 				order_ids_list = [str(cell.value) for cell in sheet['A'][1:]]
# 			except Exception as e:
# 				frappe.msgprint(f"Error reading XLSX file: {str(e)}", 'Invalid File')
# 				return
# 		elif extension == '.csv':
# 			content = file_doc.get_content()
# 			order_ids_list = content.strip().split('\n')

# 		for d in order_ids_list:
# 			if frappe.db.exists("Sales Order", {"woocommerce_id": d, "docstatus": 1}):
# 				if frappe.db.exists("Sales Invoice", {"po_no": d, "docstatus": 1}):
# 					if frappe.db.exists("Payment Entry", {"po_no": d, "docstatus": 1}):

# 						url = 'https://baahy.com/wp-json/api/gibran_user/erp_sync_status'
# 						status = 'delivered'
# 						myObj = {'id': d, 'status': status}
# 						json_data = requests.post(url, json=myObj, headers={"Content-Type":"application/json"})


# def update_order_status_after_payment(self):
# 	if frappe.db.exists('File', {'file_url': self.sales_invoice_list}):
# 		file_doc = frappe.get_doc("File", {"file_url": self.sales_invoice_list})
# 		parts = file_doc.get_extension()
# 		extension = parts[1]
# 		if extension == '.xlsx':
# 			try:
# 				content = file_doc.get_content()
# 				workbook = openpyxl.load_workbook(BytesIO(content))
# 				sheet = workbook.active
# 				order_ids_list = [str(cell.value) for cell in sheet['A'][1:]]
# 			except Exception as e:
# 				frappe.msgprint(f"Error reading XLSX file: {str(e)}", 'Invalid File')
# 				return
# 		elif extension == '.csv':
# 			content = file_doc.get_content()
# 			order_ids_list = content.strip().split('\n')

# 		counter = 0
# 		size = len(order_ids_list)

# 		for d in order_ids_list:
# 			if frappe.db.exists("Sales Order", {"woocommerce_id": d, "docstatus": 1}):
# 				if frappe.db.exists("Sales Invoice", {"po_no": d, "docstatus": 1}):
# 					if frappe.db.exists("Payment Entry", {"po_no": d, "docstatus": 1}):
# 						#updating sales order status after payment entry creation

# 						progress = counter / size * 100

# 						so = frappe.get_doc("Sales Order", {"docstatus": 1, "woocommerce_id": d})
# 						so.woocommerce_status = "delivered"
# 						so.status = "Delivered"
# 						so.db_update()

# 						url = 'https://baahy.com/wp-json/api/gibran_user/erp_sync_status'
# 						myObj = {"id": so.woocommerce_id, "status": so.woocommerce_status}
# 						json_data = requests.post(url, json=myObj, headers={"Content-Type": "application/json"})

# 						so.last_edit = today()
# 						so.db_update()

# 						frappe.db.commit()

# 						url = 'https://baahy.com/wp-json/api/gibran_user/erp_sync_status'
# 						status= 'delivered'

# 						myObj = {'id': so.woocommerce_id, 'status': status}
# 						publish_progress(percent=progress, title="Updating Order Status")
# 						json_data = requests.post(url, json=myObj, headers={"Content-Type":"application/json"})

# 						so.woocommerce_status = status
# 						so.last_edit = today()
# 						so.db_update()
# 						frappe.db.commit()
# 						so.save()
