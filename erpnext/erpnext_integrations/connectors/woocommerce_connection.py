import base64
import hashlib
import hmac
import json
import time
from frappe import publish_progress
from erpnext.utilities.bulk_transaction import transaction_processing
import frappe
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from frappe.utils import cstr
import requests
import copy
import json
from frappe.model.document import Document
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
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_company_defaults,
	get_payment_entry,
)
from erpnext.controllers.accounts_controller import update_child_qty_rate

@frappe.whitelist()
def create_to_all_pi_api(**arg):
    try:
        productJson = json.loads(frappe.request.data)
    except ValueError:
        productJson = frappe.request.data 
    ids_pr = frappe.db.get_list('Purchase Receipt' , pluck='s_code' ,filters={'s_code': ['like',  productJson.get('id')]}) 
    for id in ids_pr:
        if frappe.db.exists("Purchase Receipt",{"s_code": id,"docstatus":1}):
            pr = frappe.get_doc("Purchase Receipt", {"s_code":id ,"docstatus":1})
            transaction_processing([{"name": pr.name}],  "Purchase Receipt", "Purchase Invoice")
 

def create_to_all_pi(order_id):
    ids_pr = frappe.db.get_list('Purchase Receipt' , pluck='s_code' ,filters={'s_code': ['like', order_id]}) 
    for id in ids_pr:
        if frappe.db.exists("Purchase Receipt",{"s_code": id,"docstatus":1}):
            pr = frappe.get_doc("Purchase Receipt", {"s_code":id ,"docstatus":1})
            transaction_processing([{"name": pr.name}],  "Purchase Receipt", "Purchase Invoice")
 


def remove_all(order_id):
    done = []
    ids = frappe.db.get_list('Purchase Invoice' , pluck='s_code' ,filters={'s_code': ['like', order_id]}) 
    for id in ids:
        if frappe.db.exists("Purchase Invoice",{"s_code": id,"docstatus":1}):
            purchase_invoice = frappe.get_doc("Purchase Invoice", {"s_code": id ,"docstatus":1})
            purchase_invoice.cancel()
    ids_pr = frappe.db.get_list('Purchase Receipt' , pluck='s_code' ,filters={'s_code': ['like', order_id]}) 
    for id in ids_pr:
        if frappe.db.exists("Purchase Receipt",{"s_code": id,"docstatus":1}):
            pr = frappe.get_doc("Purchase Receipt", {"s_code":id ,"docstatus":1})
            pr.cancel()    
    # done for pr 
    # Start for po 
    ids_po = frappe.db.get_list('Purchase Order' , pluck='s_code' ,filters={'s_code': ['like', order_id]}) 
    for id in ids_po:
        if frappe.db.exists("Purchase Order",{"s_code": id,"docstatus":1}):
            pr = frappe.get_doc("Purchase Order", {"s_code":id ,"docstatus":1})
            pr.cancel()   
    
    frappe.db.commit() 







@frappe.whitelist()
def updateProuduct(**arg):
		name_list = []
		list_cat = []
		try:
			productJson = json.loads(frappe.request.data)
		except ValueError:
			productJson = frappe.request.data 
		if frappe.db.exists("Item", {"woocommerce_id": productJson.get('id')}):
		  product = frappe.get_doc("Item", {"woocommerce_id": productJson.get('id')})
		  data = productJson.get("name")
		  info = (data[:75] + '..') if len(data) > 75 else data
		  product.item_name = info#productJson.get("name")[:100] 
		  product.sku = productJson.get("sku")
		  product.woocommerce_status = productJson.get("status")
		  product.image = productJson.get("images")[0].get("src")
		  product.description = productJson.get("description")
		  product.variant_of = None 
		  if productJson.get("categories") is not None and productJson.get("categories") != []:
		    	       for item in productJson.get("categories"):
    		    	         list_cat.append({"name":item.get("name"),"id":item.get("name")})
		    	       product.item_group = list_cat[-1].get("name")
		  if productJson.get("variation") is not None and productJson.get("variation") != []:
		      for item in productJson.get("variation"):
		  					item_id = item.get('id')
		  					if frappe.db.exists("Item", {"woocommerce_id": item_id}):
		  						variation = frappe.get_doc("Item", {"woocommerce_id": item.get('id')})
		  						variation.sku = item.get("sku")
		  						variation.save()
		  product.save()
		else:
		  product = frappe.new_doc("Item")
		  product.woocommerce_id = productJson.get("id")
		  product.item_code = productJson.get("name")
		  product.item_name = productJson.get("name")
		  product.created_via = "website_api"
		  product.image = productJson.get("images")[0].get("src")
		  product.sku = productJson.get("sku")
		  product.woocommerce_status = productJson.get("status")
		  product.description = productJson.get("description")
		  if productJson.get("categories"): 
		      for item in productJson.get("categories"):
		          list_cat.append(item.get("name"))
		      check_groub(list_cat)
		      product.item_group = list_cat[-1].strip()
		  product.flags.ignore_mandatory = True
		  product.save(ignore_permissions= True)
@frappe.whitelist()
def intOrder(**arg):
	woocommerce_settings = frappe.get_doc("Woocommerce Settings")
	try:
		order = json.loads(frappe.request.data)
	except ValueError:
		order = frappe.request.data
	sys_lang = frappe.get_single("System Settings").language or "en"
	raw_billing_data = order.get("billing")
	raw_shipping_data = order.get("shipping")
	customer_name = raw_billing_data.get("first_name") + " " + raw_billing_data.get("last_name")
	payment_method_title=order.get("payment_method")
	check_mode_payment(payment_method_title)
	link_customer_and_address(raw_billing_data, raw_shipping_data, customer_name)
	link_items_int(order.get("line_items"), woocommerce_settings, sys_lang)
	customer_email=  raw_billing_data.get("email")
	create_sales_order(order, woocommerce_settings, customer_email, sys_lang ,payment_method_title)
def verify_request():
	woocommerce_settings = frappe.get_doc("Woocommerce Settings")
	sig = base64.b64encode(
		hmac.new(
			woocommerce_settings.secret.encode("utf8"), frappe.request.data, hashlib.sha256
		).digest()
	)
	if (
		frappe.request.data
		and not sig == frappe.get_request_header("X-Wc-Webhook-Signature", "").encode()
	):
		frappe.throw(_("Unverified Webhook Data"))
	frappe.set_user(woocommerce_settings.creation_user)

# function update order 
@frappe.whitelist()
def updateOrder():
	woocommerce_settings = frappe.get_doc("Woocommerce Settings")
	try:
		order = json.loads(frappe.request.data)
	except ValueError:
		# woocommerce returns 'webhook_id=value' for the first request which is not JSON
		order = frappe.request.data
	sys_lang = frappe.get_single("System Settings").language or "en"
	if frappe.db.exists("Sales Order",{"woocommerce_id": order.get('id'),"docstatus":1}):
	    order_pending = frappe.get_doc("Sales Order", {"woocommerce_id": order.get('id'),"docstatus":1})
	    if order_pending.woocommerce_status == "pending" or  order_pending.woocommerce_status == "error":
	        return frappe.throw(title="Error",msg="Order still in pending status please make sure all products available",exc=FileNotFoundError)
	raw_billing_data = order.get("billing")
	raw_shipping_data = order.get("shipping")
	customer_name = raw_billing_data.get("first_name") + " " + raw_billing_data.get("last_name")
	link_customer_and_address(raw_billing_data, raw_shipping_data, customer_name)
	update_sales_order(order, woocommerce_settings, customer_name, sys_lang)
	if order.get("status") == "wc-processing" or order.get("status") == "processing":
		updateItems(order)
	if order.get("status") == "fulfilled_order" :
		order1 = frappe.get_doc("Sales Order", {"woocommerce_id": order.get('id'),"docstatus":1})
		transaction_processing([{"name": order1.name}],  "Sales Order", "Delivery Note")
	if order.get("status") == "cancelled" or order.get("status") == "refunded" : 
	    updateItems(order)
	    if frappe.db.exists("Sales Order",{"woocommerce_id": order.get('id'),"docstatus":1}):
	        exists = frappe.get_doc("Sales Order", {"woocommerce_id": order.get('id'),"docstatus":1})
	        if exists.docstatus.is_submitted():
	            exists.cancel()
	if order.get("status") == "out_for_delivery" or order.get("status") == 'vanex':
	   if frappe.db.exists("Delivery Note", {"po_no": order.get('id')}):
	            order1 = frappe.get_doc("Delivery Note", {"po_no": order.get('id'),"docstatus":1})
	            transaction_processing([{"name": order1.name}],  "Delivery Note", "Sales Invoice")
	   else:
            order1 = frappe.get_doc("Sales Order", {"woocommerce_id": order.get('id'),"docstatus":1})
            order1.woocommerce_status = "error"
            order1.save()
            order1.reload()
	     
	if frappe.db.exists("Sales Order",{"woocommerce_id": order.get('id'),"docstatus":1}):
	    after_sync(order.get('id'), order.get("status"))
# function update order 
@frappe.whitelist()		
def updateItems(order):
	try:
		if frappe.db.exists("Sales Invoice", {"po_no": order.get('id'),"docstatus":1}):
			deliveryl = frappe.get_doc("Sales Invoice", {"po_no": order.get('id'),"docstatus":1})
			exists = frappe.get_doc("Sales Order", {"woocommerce_id": order.get('id'),"docstatus":1})
			deliveryl.po_no = exists.name
			checkPaymentEntry = deliveryl.name
			deliveryl.save(True)
			if frappe.db.exists("Payment Entry", {"reference_no": checkPaymentEntry,"docstatus":1}):
				paymentEntry = frappe.get_doc("Payment Entry", {"reference_no": checkPaymentEntry,"docstatus":1})
				if paymentEntry.docstatus.is_submitted():
					paymentEntry.cancel()
					frappe.db.commit()
			if deliveryl.docstatus.is_submitted():
				deliveryl.reload()
				deliveryl.cancel()
				frappe.db.commit()
		if frappe.db.exists("Delivery Note", {"po_no": order.get('id'),"docstatus":1}):
			deliveryl = frappe.get_doc("Delivery Note", {"po_no": order.get('id'),"docstatus":1})
			exists = frappe.get_doc("Sales Order", {"woocommerce_id": order.get('id'),"docstatus":1})
			deliveryl.po_no = exists.name
			deliveryl.save(True)
			if deliveryl.docstatus.is_submitted():
				deliveryl.reload()
				deliveryl.cancel()
				frappe.db.commit()
		remove_all(order.get('id'))
		
		
	except ValueError:	
		pass
		

def purchase_invice(order):#rawan
    if order.get("status") != "fulfilled_order" !=  order.get("status") !=  "out_for_delivery" or order.get("status") !=  'vanex' or order.get("status") !=  'delivered':
        return None



@frappe.whitelist()
def afterProc():
	woocommerce_settings = frappe.get_doc("Woocommerce Settings")
	try:
		order = json.loads(frappe.request.data)
	except ValueError:
		order = frappe.request.data
	sys_lang = frappe.get_single("System Settings").language or "en"
	raw_billing_data = order.get("billing")
	raw_shipping_data = order.get("shipping")
	customer_name = raw_billing_data.get("first_name") + " " + raw_billing_data.get("last_name")
	link_customer_and_address(raw_billing_data, raw_shipping_data, customer_name)
	update_sales_order(order, woocommerce_settings, customer_name, sys_lang)
	updateItems(order)
	addItem(order)
	purchase_invice(order)
	if order.get("status") == "fulfilled_order" :
		order1 = frappe.get_doc("Sales Order", {"woocommerce_id": order.get('id'),"docstatus":1})
		transaction_processing([{"name": order1.name}],  "Sales Order", "Delivery Note")
	if order.get("status") == "cancelled" or order.get("status") == "refunded":
            if frappe.db.exists("Delivery Note", {"po_no": order.get('id')}):
                 delivery = frappe.get_doc("Delivery Note", {"po_no": order.get('id')})
                 if delivery.docstatus.is_submitted():
                     delivery.cancel()
            if frappe.db.exists("Sales Invoice", {"po_no": order.get('id')}):
                 delivery = frappe.get_doc("Sales Invoice", {"po_no": order.get('id')})
                 if delivery.docstatus.is_submitted():
                     delivery.cancel()
            if frappe.db.exists("Sales Order",{"woocommerce_id": order.get('id'),"docstatus":1}):
			            exists = frappe.get_doc("Sales Order", {"woocommerce_id": order.get('id'),"docstatus":1})
			            if exists.docstatus.is_submitted():
			                exists.cancel()
	if order.get("status") == "out_for_delivery" or order.get("status") == 'vanex' or order.get("status") == 'delivered' or order.get("status") == 'user_returnd':
		if frappe.db.exists("Delivery Note", {"po_no": order.get('id'),"docstatus":1}):
		        order1 = frappe.get_doc("Delivery Note", {"po_no": order.get('id'),"docstatus":1})
		        transaction_processing([{"name": order1.name}],  "Delivery Note", "Sales Invoice")
		else:
			order1 = frappe.get_doc("Sales Order", {"woocommerce_id": order.get('id'),"docstatus":1})
			transaction_processing([{"name": order1.name}],  "Sales Order", "Delivery Note")
			frappe.db.commit()
			order2 = frappe.get_doc("Delivery Note", {"po_no": order.get('id'),"docstatus":1})
			transaction_processing([{"name": order2.name}],  "Delivery Note", "Sales Invoice")
	if order.get("status") == "delivered":
	    doc = frappe.get_doc("Sales Invoice", {"po_no":order.get('id')})
	    payment_entry = get_payment_entry(doc.doctype, doc.name)
	    company_details = get_company_defaults('baahy.com')
	    payment_entry.flags.ignore_mandatory = True
	    payment_entry.reference_no = doc.name
	    payment_entry.reference_date = nowdate()
	    payment_entry.cost_center = company_details.cost_center
	    payment_entry.submit()
	    frappe.db.commit()
	if frappe.db.exists("Sales Order",{"woocommerce_id": order.get('id')}):
	    after_sync(order.get('id') , order.get("status"))


@frappe.whitelist()
def deleteItem():
	try:
		order = json.loads(frappe.request.data)
	except ValueError:
		order = frappe.request.data
	code = order.get('order_id')
	code_item = order.get('item_id')

	if frappe.db.exists("Sales Order", {"woocommerce_id": code}):
		order = frappe.get_doc("Sales Order", {"woocommerce_id":code})
		item = frappe.get_doc("Item", {"woocommerce_id": code_item})
		name = order.name
		code = item.item_code
		itemOrder= frappe.get_doc('Sales Order Item',
		{
			"parent":name,
			"item_code":code,
		}
		)
		try:
			frappe.db.delete('Sales Order Item', itemOrder.name)
		except ValueError:
			pass
		order.save()


@frappe.whitelist(allow_guest=True)
def order(*args, **kwargs):
	try:
		_order(*args, **kwargs)
	except Exception:
		error_message = (
			frappe.get_traceback() + "\n\n Request Data: \n" + json.loads(frappe.request.data).__str__()
		)
		frappe.log_error("WooCommerce Error", error_message)
		raise

@frappe.whitelist()
def orderBaahy(*args, **kwargs):
	try:
		_order(*args, **kwargs)
	except Exception:
		return Exception
@frappe.whitelist(allow_guest=True)
def addItem(data):
	if frappe.db.exists("Sales Order", {"woocommerce_id": data.get('id'),"docstatus":1}):
		list=[]
		all_dis=0
		order = frappe.get_doc("Sales Order", {"woocommerce_id": data.get('id'),"docstatus":1})
		woocommerce_settings = frappe.get_doc("Woocommerce Settings")
		sys_lang = frappe.get_single("System Settings").language or "en"
		link_items_int(data.get("line_items"), woocommerce_settings, sys_lang, data.get('id'))
		for item in data.get("line_items"): 
		    sub_total = float(item.get("subtotal"))
		    price = sub_total / int(item.get("quantity"))
		    total = float(item.get("total"))
		    seller_id=item.get("seller_id")
		    disc = sub_total - total
		    disc = abs(disc)
		    if (disc >0):
		        all_dis = all_dis+disc
		    
		    cost=frappe.get_doc("Cost Center", {"woocommerce_id": seller_id})
		    cost_name = cost.name
		    woo_var_sku = item.get("sku").replace("'", "")
		    if  frappe.db.exists("Item", {"sku": woo_var_sku}):
		        woocomm_item_id = item.get("product_id")
		        woo_var_id = item.get("variation_id")
		        woo_var_sku = item.get("sku").replace("'", "")
		        found_item = frappe.get_doc("Item", {"sku": woo_var_sku})
		        found_item.cost_center=cost_name
		        
		        found_item.flags.ignore_mandatory = True
		        found_item.save()
		        
		        ordered_items_tax = item.get("total_tax")
		        list.append(
					{
					"item_code": found_item.item_code,
					"item_name": found_item.item_name,
					"before_discount":disc,
					"uom": woocommerce_settings.uom or _("Nos", sys_lang),
					"qty": item.get("quantity"),
					"rate":price,
					"warehouse": woocommerce_settings.warehouse or default_warehouse,
					"cost_center":cost_name,
					},
				)
		    else:
			    order.woocommerce_status = 'pending'
			    order.create_order_log = f'product not found sku:{woo_var_sku}'
			    
		order.discount_amount= all_dis
		order.save()
		trans_item = json.dumps(list)
		order.shipping_total=data.get("shipping_total")
		if  frappe.db.exists("Sales Taxes and Charges", {"parent": order.name,"docstatus":1}):
			tax= frappe.get_doc("Sales Taxes and Charges", {"parent": order.name,"docstatus":1})
			tax.cancel()
			tax.delete()
			order.reload()
		add_tax_details(
		order,
		data.get("shipping_total"),
		"Shipping Total",
		woocommerce_settings.f_n_f_account,
	)
		order.save()
		order.reload()
		update_child_qty_rate("Sales Order", trans_item, order.name)
		

		
		
		frappe.db.commit()
		order.flags.ignore_mandatory = True




@frappe.whitelist(allow_guest=True)
def _order(*args, **kwargs):
	woocommerce_settings = frappe.get_doc("Woocommerce Settings")
	try:
		order = json.loads(frappe.request.data)
	except ValueError:
		# woocommerce returns 'webhook_id=value' for the first request which is not JSON
		order = frappe.request.data
	event = "created"  # frappe.get_request_header("X-Wc-Webhook-Event")
	if event == "created":
		if not frappe.db.exists("Sales Order", {"woocommerce_id": order.get('id'),"docstatus":1}):
			sys_lang = frappe.get_single("System Settings").language or "en"
			raw_billing_data = order.get("billing")
			raw_shipping_data = order.get("shipping")
			customer_name = raw_billing_data.get("first_name") + " " + raw_billing_data.get("last_name")
			payment_method_title=order.get("payment_method")
			payment_method_title = check_mode_payment(payment_method_title)
			link_customer_and_address(raw_billing_data, raw_shipping_data, customer_name)
			link_items_int(order.get("line_items"), woocommerce_settings, sys_lang,order.get('id'))
			customer_email=  raw_billing_data.get("email")
		#	link_items(order.get("line_items"), woocommerce_settings, sys_lang)
			create_sales_order(order, woocommerce_settings, customer_email, sys_lang ,payment_method_title)
			if order.get("status") == "fulfilled_order" :
			    order1 = frappe.get_doc("Sales Order", {"woocommerce_id": order.get('id'),"docstatus":1})
			    transaction_processing([{"name": order1.name}],  "Sales Order", "Delivery Note")
			if order.get("status") == "out_for_delivery" or order.get("status") == "vanex" or order.get("status") == "user_returnd":
			    order1 = frappe.get_doc("Sales Order", {"woocommerce_id": order.get('id'),"docstatus":1})
			    transaction_processing([{"name": order1.name}],  "Sales Order", "Delivery Note")
			    order2 = frappe.get_doc("Delivery Note", {"po_no": order.get('id')})
			    transaction_processing([{"name": order2.name}],  "Delivery Note", "Sales Invoice")
		else: 
		    updateItems(order)
		    addItem(order)
		    sys_lang = frappe.get_single("System Settings").language or "en"
		    raw_billing_data = order.get("billing")
		    raw_shipping_data = order.get("shipping")
		    customer_name = raw_billing_data.get("first_name") + " " + raw_billing_data.get("last_name")
		    link_customer_and_address(raw_billing_data, raw_shipping_data, customer_name)
		    update_sales_order(order, woocommerce_settings, customer_name, sys_lang)
		    if order.get("status") == "wc-processing" or order.get("status") == "processing":
		        updateItems(order)
		    if order.get("status") == "fulfilled_order" :
		        order1 = frappe.get_doc("Sales Order", {"woocommerce_id": order.get('id'),"docstatus":1})
		        transaction_processing([{"name": order1.name}],  "Sales Order", "Delivery Note")
		    if order.get("status") == "cancelled" or order.get("status") == "refunded" :
		        if frappe.db.exists("Sales Invoice", {"po_no": order.get('id')}):
		            delivery = frappe.get_doc("Sales Invoice", {"po_no": order.get('id')})
		            if delivery.docstatus.is_submitted():
		                delivery.cancel()
		            if frappe.db.exists("Delivery Note", {"po_no": order.get('id'),"docstatus":1}):
		                delivery = frappe.get_doc("Delivery Note", {"po_no": order.get('id'),"docstatus":1})
		                if delivery.docstatus.is_submitted():
		                    delivery.cancel()			
		            if frappe.db.exists("Sales Order",{"woocommerce_id": order.get('id'),"docstatus":1}):
		                exists = frappe.get_doc("Sales Order", {"woocommerce_id": order.get('id'),"docstatus":1})
		                if exists.docstatus.is_submitted():
		                    exists.cancel()
		    if order.get("status") == "out_for_delivery" or order.get("status") == 'vanex':
		      if frappe.db.exists("Delivery Note", {"po_no": order.get('id'),"docstatus":1}):
		          order1 = frappe.get_doc("Delivery Note", {"po_no": order.get('id'),"docstatus":1})
		          transaction_processing([{"name": order1.name}],  "Delivery Note", "Sales Invoice")
		after_sync(order.get('id'), order.get("status"))
			            
def check_mode_payment(name):
	if not frappe.db.exists("Mode of Payment", {"woocommerce_id": name.strip()}) :
		mode_payment=frappe.new_doc("Mode of Payment")
		mode_payment.name=name
		mode_payment.mode_of_payment=name
		mode_payment.save()
		return mode_payment.name
	else:
	    mode_payment=frappe.get_doc("Mode of Payment", {"woocommerce_id": name.strip()})
	    return mode_payment.name

def link_customer_and_address(raw_billing_data, raw_shipping_data, customer_name):
	customer_woo_com_email = raw_billing_data.get("email")
	customer_exists = frappe.get_value("Customer", {"woocommerce_email": customer_woo_com_email})


	if not customer_exists:
		#	# Create Customer
		customer = frappe.new_doc("Customer")
	else:
		#	# Edit Customer
		customer = frappe.get_doc("Customer", {"woocommerce_email": customer_woo_com_email})
		old_name = customer.customer_name
	customer.customer_name = customer_name
	customer.woocommerce_email = customer_woo_com_email
	customer.flags.ignore_mandatory = True
	customer.save(ignore_permissions= True)

	if customer_exists:
	#	if old_name != customer_name:
	#		frappe.rename_doc("Customer", old_name, customer_name)
		for address_type in (
			"Billing",
			"Shipping",
		):
			try:
				address = frappe.get_doc(
					"Address", {"woocommerce_email": customer_woo_com_email, "address_type": address_type}
				)
				rename_address(address, customer)
			except (
				frappe.DoesNotExistError,
				frappe.DuplicateEntryError,
				frappe.ValidationError,
			):
				pass
	else:
		create_address(raw_billing_data, customer, "Billing")
		create_address(raw_shipping_data, customer, "Shipping")
		create_contact(raw_billing_data, customer)


def create_contact(data, customer):
    try:
	    email = data.get("email", None).replace(" ", "")
	    phone = data.get("phone", None).replace(" ", "")
	    if not email and not phone:
		    return
	    contact = frappe.new_doc("Contact")
	    contact.first_name = data.get("first_name")
	    contact.last_name = data.get("last_name")
	    contact.is_primary_contact = 1
	    contact.is_billing_contact = 1
	    contact.name = email
	    if phone:
		    contact.add_phone(phone, is_primary_mobile_no=1, is_primary_phone=1)

	    if email:
		    contact.add_email(email, is_primary=1)
	    contact.append("links", {"link_doctype": "Customer", "link_name": customer.name})
	    contact.flags.ignore_mandatory = True
	    contact.save(ignore_permissions= True)
    except:
        pass


def create_address(raw_data, customer, address_type):
	address = frappe.new_doc("Address")
	address_line1 = raw_data.get("address_1", "Not Provided")
	address_line1 =  (address_line1[:75] + '..') if len(address_line1) > 75 else address_line1
	
	address.address_line1 = address_line1
	address_line2 = raw_data.get("address_2", "Not Provided")
	address.address_line2 =  (address_line2[:75] + '..') if len(address_line2) > 75 else address_line2
	address.city = raw_data.get("city", "Not Provided")
	address.woocommerce_email = customer.woocommerce_email
	address.address_type = address_type
	address.country = frappe.get_value("Country", {"code": raw_data.get("country", "IN").lower()})
	address.state = raw_data.get("state")
	address.pincode = raw_data.get("postcode")
	address.phone = raw_data.get("phone")
	address.email_id = customer.woocommerce_email
	address.append("links", {"link_doctype": "Customer", "link_name": customer.name})
	address.flags.ignore_mandatory = True
	address.save(ignore_permissions= True)


def rename_address(address, customer):
	old_address_title = address.name
	new_address_title = customer.name + "-" + address.address_type
	address.address_title = customer.customer_name
	address.save(ignore_permissions= True)

	frappe.rename_doc("Address", old_address_title, new_address_title)


def link_items(items_list, woocommerce_settings, sys_lang):
	for item_data in items_list:
		item_woo_com_id = cstr(item_data.get("product_id"))
		item_woo_com_sku = item_data.get("sku")
		if not frappe.db.exists("Item", {"sku": item_woo_com_sku}) :
		    #frappe.db.get_value("Item",  item_woo_com_id, "woocommerce_id"):
			# Create Item
			item = frappe.new_doc("Item")
			item.item_code = _("woocommerce - {0}", sys_lang).format(item_woo_com_id)
			item.stock_uom = woocommerce_settings.uom or _("Nos", sys_lang)
			item.item_group = _("WooCommerce Products", sys_lang)
			item.regular_price = item_data.get("subtotal")
			item.item_name = item_data.get("name")[:100] 
			item.sku = item_woo_com_sku
			item.woocommerce_id = item_woo_com_id
			item.flags.ignore_mandatory = True
			item.save(ignore_permissions= True)
			
@frappe.whitelist(allow_guest=True)
def link_items_int(items_list, woocommerce_settings, sys_lang,orderId):
	items_int,items_anker,items_shik,item_chicco,item_un,item_milion,item_hakem,item_nyx,item_ser,item_agar,item_hn,item_mid,item_de,item_gm,item_lnc,item_alw,item_laa,item_gseb=[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[]
	for item_data in items_list:
		item_woo_com_id = item_data.get("sku").replace("'", "")
		if not frappe.db.exists("Item", {"sku": item_woo_com_id}):
			# and ( item_data.get("seller_id") == 33329 or item_data.get("seller_id") == 29264 or item_data.get("seller_id") == 24628 or item_data.get("seller_id") == 26005 or item_data.get("seller_id") == 31146 or item_data.get("seller_id") == 28114 or item_data.get("seller_id") == 29631 or item_data.get("seller_id") == 31174 or item_data.get("seller_id") == 28519 or item_data.get("seller_id") == 31217 or item_data.get("seller_id") == 1579 or item_data.get("seller_id") == 22508) or item_data.get("seller_id") == 45159):
			# Create Item -by rawan item_data.get("seller_id") == 28047 or 2117821178 33329 30977
			item = frappe.new_doc("Item")
			#item.cost_center=cost.name
			item.sku = item_woo_com_id
			item.item_code = item_woo_com_id
			item.stock_uom = woocommerce_settings.uom or _("Nos", sys_lang)
			item.regular_price = item_data.get("subtotal")
			lisw =  woo_cat(item_data.get("categories"),item)
			item.item_group =lisw
			data = item_data.get("name")
			info = (data[:75] + '..') if len(data) > 75 else data
			item.item_name = info
			item.woocommerce_id = item_woo_com_id
			if frappe.db.exists("Supplier", {"id_woo": item_data.get("seller_id")}):
			    supplier = frappe.get_doc("Supplier", {"id_woo": item_data.get("seller_id")})
			    item.supplier_woo=supplier.name
			if frappe.db.exists("Cost Center", {"woocommerce_id": item_data.get("seller_id")}):
			    cost=frappe.get_doc("Cost Center", {"woocommerce_id": item_data.get("seller_id")})
			    item.cost_center=cost.name
			item.flags.ignore_mandatory = True
			item.save(ignore_permissions= True)
		if(item_data.get("seller_id") == 1579):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    items_int.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})
		if(item_data.get("seller_id") == 31029):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    item_alw.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})
		if(item_data.get("seller_id") == 33329):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    item_lnc.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})
		if(item_data.get("seller_id") == 21178):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    item_gm.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})
		if(item_data.get("seller_id") == 22508):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    items_anker.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})
		if(item_data.get("seller_id") == 31174):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    items_shik.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})
		if(item_data.get("seller_id") == 28519):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    item_chicco.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})
		if(item_data.get("seller_id") == 31217):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    item_un.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})
		if(item_data.get("seller_id") == 18170):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    item_milion.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})
		if(item_data.get("seller_id") == 29631):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    item_hakem.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})
		if(item_data.get("seller_id") == 28114):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    item_ser.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})
		if(item_data.get("seller_id") == 31146):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    item_nyx.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})
		if(item_data.get("seller_id") == 26005):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    item_agar.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})
		if(item_data.get("seller_id") == 24628):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    item_hn.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})
		if(item_data.get("seller_id") == 28047):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    item_mid.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})
		if(item_data.get("seller_id") == 29264):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    item_de.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})
		if(item_data.get("seller_id") == 45159):
		    item= frappe.get_doc("Item", {"sku": item_woo_com_id})
		    item_gseb.append({'item_code': item.item_code , 'qty':item_data.get("quantity") ,'rate':item_data.get("cost")})

	if items_int is not None and items_int != []:
	    po = create_purchase_order(items_int,'baahy international', orderId)
	if item_laa is not None and item_laa != []:
	    po = create_purchase_order(item_laa,'Matlaa Alfajir', orderId)
	if item_alw is not None and item_alw != []:
	    po = create_purchase_order(item_alw,'alwatikon', orderId)
	if item_lnc is not None and item_lnc != []:
	    po = create_purchase_order(item_lnc,'LNC', orderId)
#	    transaction_processing([{"name": po.name}],  "Purchase Order", "Purchase Receipt")item_alw
	#    transaction_processing([{"name": po.name}], "Purchase Order", "Purchase Invoice")
	#  	if item_gm is not None and item_gm != []:
	#  	    po = create_purchase_order(item_gm,'Game Arena', orderId)
	#  	    transaction_processing([{"name": po.name}],  "Purchase Order", "Purchase Receipt")
	#    transaction_processing([{"name": po.name}], "Purchase Order", "Purchase Invoice")
	if items_anker is not None and items_anker != []:
	    po = create_purchase_order(items_anker,'Anker',orderId)
#	    transaction_processing([{"name": po.name}],  "Purchase Order", "Purchase Receipt")
	#    transaction_processing([{"name": po.name}], "Purchase Order", "Purchase Invoice")
	if items_shik is not None and items_shik != []:
	    po = create_purchase_order(items_shik,'الشيخ',orderId)
#	    transaction_processing([{"name": po.name}],  "Purchase Order", "Purchase Receipt")
	#    transaction_processing([{"name": po.name}], "Purchase Order", "Purchase Invoice")
	if item_chicco is not None and item_chicco != []:
	    po = create_purchase_order(item_chicco,'Chicco Libya',orderId)
#	    transaction_processing([{"name": po.name}],  "Purchase Order", "Purchase Receipt")
	#    transaction_processing([{"name": po.name}], "Purchase Order", "Purchase Invoice")
	if item_un is not None and item_un != []:
	    po = create_purchase_order(item_un,'United Electronics',orderId)
#	    transaction_processing([{"name": po.name}],  "Purchase Order", "Purchase Receipt")
	#    transaction_processing([{"name": po.name}], "Purchase Order", "Purchase Invoice") Million mobile
	if item_milion is not None and item_milion != []:
	    po = create_purchase_order(item_milion,'Million mobile',orderId)
#	    transaction_processing([{"name": po.name}],  "Purchase Order", "Purchase Receipt")
	#    transaction_processing([{"name": po.name}], "Purchase Order", "Purchase Invoice") Al Hakeem
	if item_hakem is not None and item_hakem != []:
	    po = create_purchase_order(item_hakem,'Al Hakeem',orderId)
#	    transaction_processing([{"name": po.name}],  "Purchase Order", "Purchase Receipt")
	#    transaction_processing([{"name": po.name}], "Purchase Order", "Purchase Invoice") Al Hakeem
	if item_ser is not None and item_ser != []:
	    po = create_purchase_order(item_ser,'Severin',orderId)
#	    transaction_processing([{"name": po.name}],  "Purchase Order", "Purchase Receipt")
	#    transaction_processing([{"name": po.name}], "Purchase Order", "Purchase Invoice") Al Hakeem
	if item_nyx is not None and item_nyx != []:
	    po = create_purchase_order(item_nyx,'NYX Libya',orderId)
#	    transaction_processing([{"name": po.name}],  "Purchase Order", "Purchase Receipt")
	#    transaction_processing([{"name": po.name}], "Purchase Order", "Purchase Invoice") Al Hakeem
	if item_agar is not None and item_agar != []:
	    po = create_purchase_order(item_agar,'Agar',orderId)
#	    transaction_processing([{"name": po.name}],  "Purchase Order", "Purchase Receipt")
	#    transaction_processing([{"name": po.name}], "Purchase Order", "Purchase Invoice") Al Hakeem
	if item_hn is not None and item_hn != []:
	    po = create_purchase_order(item_hn,'Hisense Libya',orderId)
#	    transaction_processing([{"name": po.name}],  "Purchase Order", "Purchase Receipt")
	#    transaction_processing([{"name": po.name}], "Purchase Order", "Purchase Invoice") Al Hakeem
	if item_mid is not None and item_mid != []:
	    po = create_purchase_order(item_mid,'Midea baahy',orderId)
#	    transaction_processing([{"name": po.name}],  "Purchase Order", "Purchase Receipt")
	#    transaction_processing([{"name": po.name}], "Purchase Order", "Purchase Invoice") Al Hakeem
	if item_de is not None and item_de != []:
	    po = create_purchase_order(item_de,'Decakila Libya',orderId)
#	    transaction_processing([{"name": po.name}],  "Purchase Order", "Purchase Receipt")
	#    transaction_processing([{"name": po.name}], "Purchase Order", "Purchase Invoice") Al Hakeem
	if item_gseb is not None and item_gseb != []:
	    po = create_purchase_order(item_gseb,'GSEB',orderId)
#	    transaction_processing([{"name": po.name}],  "Purchase Order", "Purchase Receipt")
	#    transaction_processing([{"name": po.name}], "Purchase Order", "Purchase Invoice") Al Hakeem
@frappe.whitelist()
def woo_cat_old(link, product):
    if (link is not None and link != '' ):
	    category = link.split(",")
	    liist = []
	    if len(category)> 1:
		    for cat in category:
			    list1 = cat.split(">")
			    for item in list1:
				    liist.append(item.strip())
		    import collections
		    items = [item for item, count in collections.Counter(liist).items() if count == 1 ]
		    if(len(items)>1):
		        product.woocommerce_status = "two"
		    for i in items:
			    c = frappe.get_doc("Item Group", {"id_woocommerce": int(i)})
			    name = c.name
		    print([item for item, count in collections.Counter(liist).items() if count == 1 ])
		    return name
	    else :
		    print(category)
		    for i in category:
			    c = frappe.get_doc("Item Group", {"id_woocommerce": int(i)})
			    name = c.name

		    return name
    else:
        return '5935-Uncategorizes'
@frappe.whitelist()
def all_in():
        woocommerce_settings = frappe.get_doc("Woocommerce Settings")
        order = json.loads(frappe.request.data)
        item_woo_com_id = order.get("sku")
        if not frappe.db.exists("Item", {"sku": item_woo_com_id}):
		    #frappe.db.get_value("Item",  item_woo_com_id, "woocommerce_id"):
			# Create Item
            item = frappe.new_doc("Item")
            item.sku = item_woo_com_id
            item.item_code = item_woo_com_id
            item.stock_uom = woocommerce_settings.uom or _("Nos")
            lisw =  woo_cat(order.get("categories"),item)
            item.item_group =lisw
            item.item_name = order.get("name")
            #item.woocommerce_id = order.get("id")
            item.flags.ignore_mandatory = True
            item.save(ignore_permissions= True)

@frappe.whitelist(allow_guest=True)
def create_sales_order(order, woocommerce_settings, customer_email, sys_lang,payment_method_title):
	if not frappe.db.exists("Sales Order", {"woocommerce_id": order.get("id"),"docstatus":1}) :
		new_sales_order = frappe.new_doc("Sales Order")
		customer_exists = frappe.get_value("Customer", {"woocommerce_email": customer_email})
		if  customer_exists:
			customer = frappe.get_doc("Customer", {"woocommerce_email": customer_email})
		new_sales_order.customer = customer.name
		new_sales_order.woocommerce_id = order.get("id")
		if order.get("customer_note") != "" and  order.get("customer_note") is not None:
		    new_sales_order.customer_note = order.get("customer_note")
		new_sales_order.po_no = new_sales_order.woocommerce_id = order.get("id")
		new_sales_order.naming_series = woocommerce_settings.sales_order_series or "SO-WOO-"
		created_date = order.get("date_created").split("T")
		new_sales_order.transaction_date = created_date[0]
		delivery_after = woocommerce_settings.delivery_after_days or 7
		new_sales_order.delivery_date = frappe.utils.add_days(created_date[0], delivery_after)
		new_sales_order.companys = 'baahy.com'
		new_sales_order.last_edit =today() 
		new_sales_order.mode_of_payment =payment_method_title.strip()
		new_sales_order.delivery_driver = order.get("assign_to")
		new_sales_order.woocommerce_status=order.get("status")
		new_sales_order.shipping_total=order.get("shipping_total")
		shipping_lines = order.get("shipping_lines")
		for shipping_line in shipping_lines:
			new_sales_order.shipping_city=shipping_line.get("method_title")
		set_items_in_sales_order(new_sales_order, woocommerce_settings, order, sys_lang)
		new_sales_order.flags.ignore_mandatory = True
		new_sales_order.insert(ignore_permissions = True)
		new_sales_order.submit()
		frappe.db.commit()



def set_items_in_sales_order(new_sales_order, woocommerce_settings, order, sys_lang):
	company_abbr = frappe.db.get_value("Company", woocommerce_settings.company, "abbr")
	all_dis = 0 
	default_warehouse = _("Stores - {0}", sys_lang).format(company_abbr)
	if not frappe.db.exists("Warehouse", default_warehouse) and not woocommerce_settings.warehouse:
		frappe.throw(_("Please set Warehouse in Woocommerce Settings"))
	"""_summary_
	"""
	for item in order.get("line_items"):
		woocomm_item_id = item.get("product_id")
		woo_var_id = item.get("variation_id")
		woo_var_sku = item.get("sku").replace("'", "")
		ordered_items_tax = item.get("total_tax")
		item_woo_com_id = item.get("sku").replace("'", "")
		seller_id = item.get("seller_id")
		sub_total = float(item.get("subtotal"))
		total = float(item.get("total"))
		price = sub_total / int(item.get("quantity"))
		cost=frappe.get_doc("Cost Center", {"woocommerce_id": seller_id})
		disc = sub_total - total
		if  frappe.db.exists("Item", {"sku": item_woo_com_id}) :
		    found_item = frappe.get_doc("Item", {"sku": woo_var_sku})
		    new_sales_order.append(
				"items",
				{
					"item_code": found_item.item_code,
					"item_name": found_item.item_name,
					"description": found_item.item_name,
					"before_discount":disc,
					"delivery_date": new_sales_order.delivery_date,
					"uom": woocommerce_settings.uom or _("Nos", sys_lang),
					"qty": item.get("quantity"),
					"rate":price,
					"warehouse": woocommerce_settings.warehouse or default_warehouse,
					"cost_center": cost.name,
				},
			)
		else:
		    new_sales_order.woocommerce_status = 'pending'
		    new_sales_order.create_order_log = f'product not found sku:{item_woo_com_id}'
		if (disc >0 ):
			all_dis = all_dis+disc
		    #add_tax_details(
			#    new_sales_order, disc, "Ordered Item tax", woocommerce_settings.discount_account
		    #)
	new_sales_order.discount_amount= all_dis
	# shipping_details = order.get("shipping_lines") # used for detailed order

	#add_tax_details(
	#	new_sales_order, order.get("shipping_tax"), "Shipping Tax", woocommerce_settings.f_n_f_account
	#)
	add_tax_details(
		new_sales_order,
		order.get("shipping_total"),
		"Shipping Total",
		woocommerce_settings.f_n_f_account,
	)

def add_tax_details(sales_order, price, desc, tax_account_head):
	sales_order.append(
		"taxes",
		{
			"charge_type": "Actual",
			"account_head": tax_account_head,
			"tax_amount": price,
			"description": desc,
		},
	)

@frappe.whitelist(allow_guest=True)
def update_sales_order(order, woocommerce_settings, customer_name, sys_lang):
	if frappe.db.exists("Sales Order", {"woocommerce_id": order.get('id'),"docstatus":1}):
		new_sales_order = frappe.get_doc("Sales Order", {"woocommerce_id":order.get('id'),"docstatus":1})
		new_sales_order.flags.ignore_mandatory = True
		new_sales_order.woocommerce_status= _(f"{order.get('status')}","en")
		new_sales_order.woocommerce_id = order.get("id")
		if order.get("customer_note") !="" and order.get("customer_note") is not None:
		    new_sales_order.customer_note=order.get("customer_note")
		new_sales_order.shipping_total=order.get("shipping_total")
		new_sales_order.delivery_driver = order.get("assign_to")
		new_sales_order.last_edit =today() 
		payment_method_title=order.get("payment_method")
		payment_method_title = check_mode_payment(payment_method_title)
		if ( payment_method_title == "Cash On Delivery" and order.get('status') == "vanex"):
			new_sales_order.mode_of_payment = "Vanex"
		else:
			new_sales_order.mode_of_payment = payment_method_title  
		if frappe.db.exists("Delivery Note", {"po_no": order.get('id'),"docstatus":1}):
			delvery =  frappe.get_doc("Delivery Note", {"po_no": order.get('id'),"docstatus":1})
			if ( payment_method_title == "Cash On Delivery" and order.get('status') == "vanex"):
				delvery.mode_of_payment = "Vanex"
			else:
				delvery.mode_of_payment = payment_method_title
			delvery.save(ignore_permissions = True)

		shipping_lines = order.get("shipping_lines")
		for shipping_line in shipping_lines:
			    new_sales_order.shipping_city=shipping_line.get("method_title")
		
		
		new_sales_order.save(ignore_permissions = True)

@frappe.whitelist(allow_guest=True)
def change_status(checked_items, status):
	if isinstance(checked_items, str):
		deserialized_data = json.loads(checked_items)
	else:
		deserialized_data = checked_items
	company_details = get_company_defaults('baahy.com')
	if status == 'payment_entry':
		counter = 0
		size = len(deserialized_data)

		for order in deserialized_data :  
			try:
				if frappe.db.exists("Sales Invoice", {"po_no": order.get('po_no')}):
					doc = frappe.get_doc("Sales Invoice", {"po_no":order.get('po_no')})
					woocommerce_id = order.get('po_no')
				else:
					doc = frappe.get_doc("Sales Invoice", {"po_no":order.get('woocommerce_id')})
					woocommerce_id = order.get('woocommerce_id')
					sync_order_status_pi(woocommerce_id)
				progress = counter / size * 100
				payment_entry = get_payment_entry(doc.doctype, doc.name)
				payment_entry.flags.ignore_mandatory = True
				payment_entry.reference_no = doc.name
				payment_entry.reference_date = nowdate()
				payment_entry.po_no=woocommerce_id
				payment_entry.cost_center = company_details.cost_center
				payment_entry.submit()
				frappe.db.commit()
				counter = counter + 1
				url = 'https://baahy.com/wp-json/api/gibran_user/erp_sync_status'
				status= 'delivered'
				
				if frappe.db.exists("Sales Order", {"woocommerce_id":order.get('po_no'),"docstatus":1}):
					salesOrder = frappe.get_doc("Sales Order", {"woocommerce_id":order.get('po_no'),"docstatus":1})
				else:
					salesOrder = frappe.get_doc("Sales Order", {"woocommerce_id":order.get('woocommerce_id'),"docstatus":1})
				name = salesOrder.name
				myObj = {'id': woocommerce_id, 'status': status}
				publish_progress(percent=progress, title="Creating Payment Entry")
				json_data= requests.post(url, json=myObj, headers={'Content-Type': 'application/json'})
				salesOrder.woocommerce_status = status
				salesOrder.last_edit = today() 
				salesOrder.save()
				#frappe.db.sql(f"""UPDATE  `tabSales Order` SET `woocommerce_status` = '{status}' WHERE `tabSales Order`.`name` = '{name}';""")  
			except ValueError:
				counter = counter - 1
		frappe.msgprint(_(f'{counter} Payment Entry Created successfully'), alert=True)
		return counter

	#transaction_processing([{"name": payment.name}],  "Sales Invoice", "Payment Entry")
	for order in deserialized_data : 
		name = order.get('name')
		woocommerce_id = order.get('woocommerce_id')
		statusOrder = order.get('woocommerce_status')
		if((statusOrder == 'confirmed' and status == 'item_out_of_stock') or (statusOrder == 'confirmed' and status == 'fulfilled_order') ):
			url = 'https://baahy.com/wp-json/api/gibran_user/erp_sync_status'
			myObj = {
				"id": woocommerce_id,
				"status":status,}
			json_data= requests.post(url , json=myObj , headers={"Content-Type":"application/json"})
			sale_order = frappe.get_doc("Sales Order", {"woocommerce_id": woocommerce_id ,"docstatus":1})
			sale_order.woocommerce_status = status
			sale_order.last_edit = today() 
			sale_order.save()
		elif(statusOrder == 'return_to_stock' and status == 'cancelled' ):
			myObj = {
				"id": woocommerce_id,
				"status":status,}
			updateItems(myObj)
			if frappe.db.exists("Sales Order",{"woocommerce_id": woocommerce_id,"docstatus":1}):
				exists = frappe.get_doc("Sales Order", {"woocommerce_id": woocommerce_id ,"docstatus":1})
				exists.woocommerce_status = status
				exists.last_edit = today() 
				exists.save()
				exists.reload()
				if exists.docstatus.is_submitted():
					exists.cancel()
					frappe.db.commit()
			if frappe.db.exists("Purchase Receipt",{"s_code": woocommerce_id,"docstatus":1}):
				purchase_receipt = frappe.get_doc("Purchase Receipt", {"s_code": woocommerce_id ,"docstatus":1})
				purchase_receipt.cancel()
				purchase_order = frappe.get_doc("Purchase Order", {"s_code": woocommerce_id ,"docstatus":1})
				purchase_order.cancel()
				frappe.db.commit()
			url = 'https://baahy.com/wp-json/api/gibran_user/erp_sync_status'
			json_data= requests.post(url , json=myObj , headers={"Content-Type":"application/json"})
		elif(statusOrder == 'delivered' and status == 'completed'):
			url = 'https://baahy.com/wp-json/api/gibran_user/erp_sync_status'
			myObj = {
				"id": woocommerce_id,
				"status":status,}
			json_data= requests.post(url , json=myObj , headers={"Content-Type":"application/json"})
			sale_order = frappe.get_doc("Sales Order", {"woocommerce_id": woocommerce_id,"docstatus":1 })
			sale_order.woocommerce_status = status
			sale_order.last_edit = today() 
			sale_order.save()
			
			frappe.db.commit()
		else:
			frappe.throw(_(f"You are not allowed to change the order status from {statusOrder} to {status} "))
	frappe.db.commit()

def sync_order_status_pi(order_id):
    done = []
    ids = frappe.db.get_list('Purchase Invoice' , pluck='s_code' ,filters={'s_code': ['like', order_id]})
    for id in ids:
        if frappe.db.exists("Sales Order",{"woocommerce_id": id,"docstatus":1}) and  frappe.db.exists("Purchase Invoice",{"s_code": id,"docstatus":1}):
            order = frappe.get_doc("Sales Order", {"woocommerce_id": id,"docstatus":1})
            pi = frappe.get_doc("Purchase Invoice", {"s_code": id,"docstatus":1})
            pi.order_status = order.woocommerce_status
            pi.save()
        done.append("done")
    frappe.db.commit()
    return done


def after_sync(order_id , order_status ,page ='' ):
    if frappe.db.exists("Purchase Invoice",{"s_code": order_id}):
        sync_order_status_pi(order_id)
    
    url = 'https://baahy.com/wp-json/api/gibran_user/erpnext_sync_done'
    body= {
        "order_id":order_id,
    }
    while page == '':
        try:
            page= requests.post(url , json=body , headers={"Content-Type":"application/json"})
            break
        except:
            print("Connection refused by the server..")
            time.sleep(5)
            continue
    
    #SELECT `tabPurchase Order`.`supplier` FROM `tabPurchase Order` GROUP BY `tabPurchase Order`.`supplier`

  




@frappe.whitelist(allow_guest=True)
def error_status(*args, **kwargs):
    woocommerce_settings = frappe.get_doc("Woocommerce Settings")
    try:
        order = json.loads(frappe.request.data)
    except ValueError:
        order = frappe.request.data
    woocommerce_id= order.get("id")
    if frappe.db.exists("Sales Order", {"woocommerce_id": woocommerce_id,"docstatus":1}):
        sale_order = frappe.get_doc("Sales Order", {"woocommerce_id": woocommerce_id,"docstatus":1 })
        sale_order.woocommerce_status = "error"
        sale_order.last_edit = today() 
        sale_order.save()

#update Or create Item Group - By Rania 
@frappe.whitelist(allow_guest=True)
def sync_item_group():
    try:
        category= json.loads(frappe.request.data)
    except:
        category = frappe.request.data 
    woocommerce_id = category.get("term_id")
    if frappe.db.exists("Item Group", {"id_woocommerce": woocommerce_id}):
        select = frappe.get_doc("Item Group", {"id_woocommerce": woocommerce_id})
    else :
        select = frappe.new_doc("Item Group")
        select.item_group_name = category.get("name")
    select.id_woocommerce = woocommerce_id
    select.name_woocommerce = category.get("name").lower()
    if frappe.db.exists("Item Group", {"id_woocommerce": category.get("parent")}):
        parent = frappe.get_doc("Item Group", {"id_woocommerce":  category.get("parent") })
        select.parent_item_group = parent.name 
    else:
        select.parent_item_group = 'Categories'
    select.save()
    frappe.db.commit()
#update Or create Supplier / Cost Center - By Rania 
@frappe.whitelist(allow_guest=True)
def sync_cost_supplier():
    #cost 
    try:
        seller= json.loads(frappe.request.data)
    except:
        seller = frappe.request.data 
    woocommerce_id = seller.get("ID")
    if frappe.db.exists("Cost Center", {"woocommerce_id": woocommerce_id}):
        select = frappe.get_doc("Cost Center", {"woocommerce_id": woocommerce_id})
    else :
        select = frappe.new_doc("Cost Center")
        select.cost_center_name = seller.get("display_name")
    select.parent_cost_center = '120 - baahy Vendors - b'
    select.woocommerce_id = woocommerce_id
    select.name_woocommerce = seller.get("display_name").lower()
    select.save()
    #Supplier
    if frappe.db.exists("Supplier", {"id_woo": woocommerce_id}):
        supplier = frappe.get_doc("Supplier", {"id_woo": woocommerce_id})
    else :
        supplier = frappe.new_doc("Supplier")
        supplier.supplier_name = seller.get("display_name")
        supplier.is_group = 1
    supplier.supplier_group = 'Vendors Local'
    supplier.id_woo = woocommerce_id
    supplier.supplier_type = 'Company'
    supplier.save()
    frappe.db.commit()



#### rawan 

#
def create_purchase_order(item_cool ,supplier , shipment_code):
    supplier_cost=frappe.get_doc("Supplier", {"name": supplier})
    
    
    woocommerce_settings = frappe.get_doc("Woocommerce Settings")
    po = frappe.new_doc("Purchase Order")
    po.s_code = shipment_code
    po.schedule_date = add_days(nowdate(), 1)
    po.supplier = supplier
    po.is_subcontracted =  0
    po.currency =  'LYD'
    po.conversion_factor =  0
    po.supplier_warehouse =  None
    po.set_warehouse =  woocommerce_settings.warehouse
    cost=frappe.get_doc("Cost Center", {"woocommerce_id": supplier_cost.id_woo})
    po.cost_center=cost.name
    for item in item_cool:
        po.append(
				"items",
				{
					"item_code": item.get("item_code"),
					"qty": item.get('qty'),
					"rate":  item.get('rate'),
					"received_qty":0,
					"schedule_date": add_days(nowdate(), 1),	
					"cost_center":cost.name
				},
			)
			
    
    
    po.flags.ignore_mandatory = True
    
    
    
    po.set_missing_values()
    


    po.insert()
    
    
    po.submit()
    
    
    frappe.db.commit()
	

#	po.notify_update()

    return po

def create_purchase_order_import(item_cool ,supplier , shipment_code):
    supplier_cost=frappe.get_doc("Supplier", {"name": supplier})
    
    
    woocommerce_settings = frappe.get_doc("Woocommerce Settings")
    po = frappe.new_doc("Purchase Order")
    po.s_code = "import"
    po.schedule_date = add_days(nowdate(), 1)
    po.supplier = supplier
    po.is_subcontracted =  0
    po.currency =  'LYD'
    po.conversion_factor =  0
    po.supplier_warehouse =  None
    po.set_warehouse =  woocommerce_settings.warehouse
    cost=frappe.get_doc("Cost Center", {"woocommerce_id": supplier_cost.id_woo})
    po.cost_center=cost.name
    for item in item_cool:
        po.append(
				"items",
				{
					"item_code": item.get("item_code"),
					"qty": item.get('qty'),
					"rate":  item.get('rate'),
					"received_qty":0,
					"schedule_date": add_days(nowdate(), 1),	
					"cost_center":cost.name
				},
			)
			
    
    
    po.flags.ignore_mandatory = True
    
    
    
    po.set_missing_values()
    


    po.insert()
    
    
#    po.submit()
    
    
    frappe.db.commit()
	

#	po.notify_update()

    return po

@frappe.whitelist(allow_guest=True)
def long_job(self):
	frappe.publish_realtime('msgprint', 'Starting long job...')
	counter=0 
	indSize = None
	indexCategories = None
	item_list = []
	indexcost= None
	indexSellerSKU=None
	item_cool = []
	indexBrand = None
	indexSize=None
	indexVarSKU=None
	indexQuantity=None
	indexSSKU=None
	indexImages=None
	indColor = None
	indexName=None
	indexColor=None
	indexVendor = None
	cost=None
	supplier12=None
	indSize = None
	indSold = None
	indexSold = None
	item_cool=[]
	shipment_code=None
	shipment_code_ind=None
	indBrand = None
	indexDescription = '' #('/Users/macbookpro/frappe/erpnext/frappe-bench/sites/erpnext.local/'+self.import_file, "r")('/cloudclusters/erpnext/frappe-bench/sites/default/'+self.import_file, "r") 
	with open('/cloudclusters/erpnext/frappe-bench/sites/default/'+self.import_file, "r")   as file:
		csvreader = csv.reader(file)
		ides=[]
		hedold =next(csvreader)
		hed = [item for item in hedold]
		for col in hed:
			col = col.strip()
			print("rere")
			if col in ['shipment code','Shipment Code','Vendor/Supplier','Quantity','Supplier','Vendor','Categories','Tags',	'Tags/Categories'	,'Name',	'Descreption',	'Brand',	'SKU',	'Seller SKU',	'Color'	,'Images'	,'Cost LD'	,'cost ld','Price',	'sale price',	'Sold By',	'Size',	'Quantity',	'Title'	,'Variation SKU'	,'ID'	,'Low Stock']:

				if col == 'ID':
					idexID = hed.index(col)
				if col == 'shipment code' or col == 'Shipment Code':
					shipment_code_ind = hed.index(col)
				elif col== 'Vendor/Supplier' or col== 'Supplier' or col== 'Vendor' or col.lower()=='vendor/supplier' :
					indexVendor = hed.index(col)
					print(f"indexVendor {col} == {indexVendor}")
				
				elif col == 'SKU' or col == 'sku':
					indexSSKU = hed.index(col)
				elif  col== 'Name' or  col== 'name':
					indexName = hed.index(col)
				elif col == 'description' or col =='description':
					indexDescription =hed.index(col)
				elif col == 'Size' :
					indexSize =hed.index(col) 
				elif col == 'Cost LD' or col == 'cost ld':
					indexcost =hed.index(col) 
				elif col == 'Categories' or col == 'Tags' or  col == 'Tags/Categories' :
					indexCategories =hed.index(col) 
				elif col == 'Brand' or col == 'brand':
					indexBrand =hed.index(col) 
				elif col == 'Seller SKU':
					indexSellerSKU =hed.index(col) 
				elif col == 'Color' :
					indexColor =hed.index(col) 
				elif col == 'Images' :
					indexImages =hed.index(col) 
				elif col == 'Variation SKU' :
					indexVarSKU =hed.index(col) 
				elif col == 'Sold By' :
					indexSold =hed.index(col) 
				elif col == 'Quantity' :
					indexQuantity =hed.index(col) 
		for row in csvreader:
			item_list.append({'soldby':row[indexSold] if indexSold or indexSold == 0 else '' ,'shipment_code':row[shipment_code_ind] if shipment_code_ind or shipment_code_ind == 0 else '' ,'Cost':row[indexcost] if indexcost or indexcost == 0  else '' ,'category':row[indexCategories] if indexCategories or indexCategories == 0  else '' ,'supplier': row[indexVendor].strip().lower() if indexVendor  or indexVendor == 0  else '' ,'name':row[indexName] if indexName or indexName == 0  else '','brand':row[indexBrand] if indexBrand or indexBrand == 0  else '','seller_sku':row[indexSellerSKU] if indexSellerSKU or indexSellerSKU == 0 else '','color':row[indexColor] if indexColor or indexColor == 0 else '','size':row[indexSize] if indexSize or indexSize == 0  else '','_sku':row[indexSSKU] if indexSSKU or indexSSKU == 0 else '','Descreption':row[indexDescription]  if indexDescription  or indexDescription == 0  else '','var_sku':row[indexVarSKU] if indexVarSKU or indexVarSKU == 0  else '' , 'Images' :row[indexImages] if  indexImages  or indexImages == 0 else '' , 'qty':row[indexQuantity] if  indexQuantity or indexQuantity == 0 else ''})                                                                                      
		for row in item_list:
			sku = row.get('_sku')
			if row.get('shipment_code') is not None and row.get('shipment_code') !='':
			    shipment_code = row.get('shipment_code')
			if sku != '':
				if  frappe.db.exists("Item",{'item_code':row.get('_sku').strip()}):
					item = frappe.get_doc("Item", {'item_code':row.get('_sku').strip()})
					item.sku=row.get('_sku').strip()
				else:
				  item = frappe.new_doc("Item")
				  item.sku = row.get('_sku').strip()
				  item.item_code =  row.get('_sku').strip()
				if row.get('Images'):
					image_links = row.get('Images').split(",")
					item.image = image_links[0]
				if row.get("seller_sku"):
					item.seller_sku= row.get("seller_sku")
				lisw =  woo_cat(row.get("category"),item)
				item.item_group =lisw#category[-1].strip()#item_data.get("category")
				if row.get("Cost"):
					item.cost=row.get("Cost")
				if row.get("brand"):
					item.brand_product =  row.get("brand")
					check_brand(row.get("brand"))
					item.brand=row.get("brand").strip().lower()

				if row.get("size"):
					isIn = frappe.db.sql(f"""SELECT * FROM `tabItem Variant Attribute`  WHERE  `tabItem Variant Attribute`.`attribute` ='Size' AND `tabItem Variant Attribute`.`parent` ='{sku}';""")
					add_att_value(row.get("size"),'Size')	
					print(f"sizesize {isIn}")
					if isIn == '' or isIn == () or isIn is None:
						print(f"sizesize12 {isIn}")
						item.append("attributes",
							{
							"attribute": 'Size',
							'attribute_value': row.get("size"),
							'attribute_option': row.get("size")
							}
							)
				if row.get("name"):
					data = row.get("name")
					info = (data[:75] + '..') if len(data) > 75 else data
					item.item_name = info
				if row.get("Descreption"):
					item.description = row.get("Descreption")
				if row.get("var_sku"):
					item.has_variants = 1
				if row.get("supplier"):
					supplier = row.get("supplier")
					if  frappe.db.exists("Supplier",{'id_woo':row.get("supplier")}):
						supplier = frappe.get_doc("Supplier", {"id_woo": row.get("supplier")})
						item.supplier_woo = supplier.name
						supplier12 =  supplier.name
					else:
						doc = frappe.get_doc(
						{
					                    "doctype": "Supplier",
					                    "supplier_name": row.get("supplier"),
					                    "id_woo":row.get("supplier"),
					                    "supplier_group": "Vendors Local",
					                    "supplier_type":  "Company",
						}
						).insert()
						item.supplier_woo =doc.name
						supplier12=doc.name
					check_for_cost_center(supplier12)
					cost=frappe.get_doc("Cost Center", {"woocommerce_id": row.get("supplier")})
					item.cost_center=cost.name
				item.flags.ignore_mandatory = True
				item.save(ignore_permissions= True)
			#	frappe.db.commit()
				itemCode = item.item_code 
				if row.get("var_sku"):
					if not frappe.db.exists("Item",{'item_code':row.get("var_sku")}):
						print(f"Here is {row.get('var_sku')} -- {row.get('size')}")
						variant = create_variant(item.name, {"Size": row.get("size")})
						variant.item_code =row.get("var_sku")
						variant.sku = row.get("var_sku")
						variant.cost_center= cost.name
						variant.save()
						itemCode = variant.item_code
						
					else:
						vtem = frappe.get_doc("Item", {'item_code':row.get('var_sku')})
						
						
						if cost is not None:
						    
						    
						    vtem.cost_center= cost.name
						else:
						    
						    cost=frappe.get_doc("Cost Center", {"cost_center_name": supplier12})
						    vtem.cost_center= cost.name
							
							
						itemCode = vtem.item_code
				item_cool.append({'item_code': itemCode , 'qty':row.get("qty") ,'rate':row.get("Cost") ,'cost_center':cost.name})
				frappe.db.commit()
		check_for_cost_center(supplier12)
		create_purchase_order_import(item_cool ,supplier12,shipment_code )
		frappe.db.commit()


def add_att_value(item_data,type):
	item_attr = frappe.get_doc("Item Attribute", type)
	print(item_attr.item_attribute_values)
	isIn = frappe.db.sql(
	f"""
	SELECT * FROM `tabItem Attribute Value` WHERE `tabItem Attribute Value`.`attribute_value` ='{item_data}'
	"""
	)


	if isIn is None or isIn == () or isIn == '':
		item_attr = set_new_attribute_values(item_attr, item_data)
	item_attr.save()	

def set_new_attribute_values(item_attr, values):
    item_attr.append("item_attribute_values",{"attribute_value": values,"abbr": values})
    return item_attr
 
def woo_cat(link, product):
	try:
		category = link.split(",")
		liist = []
		if len(category)> 1:
			for i in category:
				counter = category.index(i)
				liist.append({
					'id': counter,
					'parent' : 0 if counter == 0 else category[counter-1].lower().strip(),
					'name':i.lower().strip()
				})
			lastCat = liist[-1]
			if frappe.db.exists("Item Group", {'name_woocommerce' : lastCat.get("parent")}):
				paren =frappe.get_doc("Item Group", {'name_woocommerce' : lastCat.get("parent")})
				if frappe.db.exists("Item Group", {'name_woocommerce' : lastCat.get("name"),'parent_item_group' : paren.name}):
					cate =frappe.get_doc("Item Group", {'name_woocommerce' : lastCat.get("name"),'parent_item_group' : paren.name})
				else:
					return '5935-Uncategorizes'
				return cate.name
			else:
				return '5935-Uncategorizes'
		else :
			if frappe.db.exists("Item Group", {'name_woocommerce' : lastCat.get("name")}):
				cate =frappe.get_doc("Item Group", {'name_woocommerce' : lastCat.get("name")})
				return  cate.name
	except Exception as e:
		return '5935-Uncategorizes'
def check_brand(data):
    if data is not None and data != '':
        brand_name = data
        if not frappe.db.exists("Brand", {"brand": brand_name.strip().lower()}):
            brand = frappe.new_doc("Brand")
            brand.brand = brand_name.strip().lower()
            brand.insert()
            brand.save()
def check_for_cost_center(supplier):
    if frappe.db.exists("Supplier",{'name':supplier}):
        supplier1= frappe.get_doc("Supplier", {"name": supplier})
        supplierCode= supplier1.id_woo
        if frappe.db.exists("Cost Center", {"woocommerce_id": supplierCode}):
            select = frappe.get_doc("Cost Center", {"woocommerce_id": supplierCode})
        else:
            frappe.get_doc({
                "doctype": "Cost Center",
                "cost_center_name": supplier1.name,
                "parent_cost_center": "120 - baahy Vendors - b",
                "company":"baahy.com",
                "woocommerce_id":supplierCode,
                "is_group": 0,
                 
            }).insert(ignore_permissions=True)



@frappe.whitelist(allow_guest=True)
def long_job_old(self):
    with open('/cloudclusters/erpnext/frappe-bench/sites/default/'+ self.import_file, "r")   as file:
        csvreader = csv.reader(file)
        hedold =next(csvreader)
        for row in csvreader:
            if  frappe.db.exists("Item",{'item_code':row[0]}):
                item = frappe.get_doc("Item", {'item_code':row[0]})
                if  frappe.db.exists("Item",{'item_code':row[1]}):
                    paremt_item = frappe.get_doc("Item", {'item_code':row[1]})
                    item.variant_of = paremt_item.name
                    item.save()
                    frappe.db.commit()
        
                    
@frappe.whitelist(allow_guest=True)
def sync_order_status():
    done = []
    ids = frappe.db.get_list('Purchase Invoice' , pluck='s_code' ,filters={'s_code': ['like', '%1%']})
    for id in ids:
        if frappe.db.exists("Sales Order",{"woocommerce_id": id,"docstatus":1}) and  frappe.db.exists("Purchase Invoice",{"s_code": id,"docstatus":1}):
            order = frappe.get_doc("Sales Order", {"woocommerce_id": id,"docstatus":1})
            pi = frappe.get_doc("Purchase Invoice", {"s_code": id,"docstatus":1})
            pi.order_status = order.woocommerce_status
            pi.save()
            done.append("done")
    frappe.db.commit()
    return done
            

@frappe.whitelist(allow_guest=True)
def sync_sales_invoice_status():
	ids = frappe.db.get_list('Sales Invoice' ,pluck='po_no' , filters={'delivery_driver': ['like', ''] , 'po_no':['like', '%112%']}, ignore_permissions=True)
	for id in ids:
		if frappe.db.exists("Sales Order", {"woocommerce_id": id, "docstatus": 1}) and frappe.db.exists("Sales Invoice", {"po_no": id, "docstatus": 1}):
			order = frappe.get_doc("Sales Order", {"woocommerce_id": id, "docstatus":1})
			si = frappe.get_doc("Sales Invoice", {"po_no": id, "docstatus": 1})
			if(order.delivery_driver != '' and order.delivery_driver is not None):
				si.delivery_driver = order.delivery_driver
				si.db_update()
				frappe.db.commit()
	return ids


def sync_invoice_status(self, method):
	ids = frappe.db.get_list('Sales Invoice' ,pluck='po_no' , filters={'delivery_driver': ['like', ''] , 'po_no':['like', '%112%']}, ignore_permissions=True)
	for id in ids:
		if frappe.db.exists("Sales Order", {"woocommerce_id": id, "docstatus": 1}) and frappe.db.exists("Sales Invoice", {"po_no": id, "docstatus": 1}):
			order = frappe.get_doc("Sales Order", {"woocommerce_id": id, "docstatus":1})
			si = frappe.get_doc("Sales Invoice", {"po_no": id, "docstatus": 1})
			if(order.delivery_driver != '' and order.delivery_driver is not None):
				si.delivery_driver = order.delivery_driver
				si.db_update()
				frappe.db.commit()
	return ids


@frappe.whitelist(allow_guest=True)
def sync_purchase_invoice_status():
	ids = frappe.db.get_list('Purchase Invoice', pluck='s_code' , filters={'s_code': ['like', '%112%']}, ignore_permissions=True)
	for id in ids:
		if frappe.db.exists("Sales Order", {"woocommerce_id": id, "docstatus": 1}) and frappe.db.exists("Purchase Invoice", {"s_code": id, "docstatus": 1}):
			order = frappe.get_doc("Sales Order", {"woocommerce_id": id, "docstatus":1})
			pi = frappe.get_doc("Purchase Invoice", {"s_code": id, "docstatus": 1})
			if pi.order_status != order.woocommerce_status:
				pi.order_status = order.woocommerce_status
				pi.db_update()
				frappe.db.commit()


@frappe.whitelist(allow_guest=True)
def updateErrors():
    done = []
    ids = frappe.db.get_list('Sales Order' , pluck='woocommerce_id' ,filters={'woocommerce_status': ['like', 'error']})
    for id in ids:
        if frappe.db.exists("Sales Order",{"woocommerce_id": id,"docstatus":1}) :
            myObj = {"id": id}
            json_data= requests.post("https://baahy.com/wp-json/api/gibran_user/erpnext_sync_error" , json=myObj , headers={"Content-Type":"application/json"})
        done.append("done")
    return done


@frappe.whitelist(allow_guest=True)
def sync_sales_status():
    done = []
    ids = frappe.db.get_list('Sales Invoice' , pluck='po_no' ,filters={
        'delivery_driver':['like', ''] ,
        'po_no':['like', '%112%']
        
    })
    for id in ids:
        if frappe.db.exists("Sales Order",{"woocommerce_id": id,"docstatus":1}) and  frappe.db.exists("Sales Invoice",{"po_no": id,"docstatus":1}):
            order = frappe.get_doc("Sales Order", {"woocommerce_id": id,"docstatus":1})
            pi = frappe.get_doc("Sales Invoice",{"po_no": id,"docstatus":1})
            if(order.delivery_driver != '' and order.delivery_driver is not None):
                pi.delivery_driver = order.delivery_driver
                pi.save()
                done.append("done")
                frappe.db.commit()
                
    return ids


@frappe.whitelist(allow_guest=True)
def sync_cancelled_status():
    cancelled_ids = frappe.db.get_list('Sales Order', filters={'docstatus': 2, 'woocommerce_status': 'error'})
    for id in cancelled_ids:
        cancelled_order = frappe.get_doc("Sales Order", id.get('name'))
        cancelled_order.woocommerce_status = 'cancelled'
        cancelled_order.db_update()
        frappe.db.commit()
