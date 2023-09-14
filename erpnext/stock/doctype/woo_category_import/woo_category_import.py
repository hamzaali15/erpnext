
from unicodedata import category
from frappe.model.document import Document
import frappe
import csv
from frappe import _

class WooCategoryImport(Document):
	def after_insert(self):
		item_list = []
		with open('/cloudclusters/erpnext/frappe-bench/sites/default/'+self.import_file, "r") as file:
			csvreader = csv.reader(file)
			#for col in hed:'/cloudclusters/erpnext/frappe-bench/sites/default/'
			#	print(f"fffff {col.lower()}")
			#	if col in ['id_name', 'name', 'parent']:
			#		print(f"fffff {col.lower()}")
			#		if col.lower().strip() == 'id_name':
			#			print(f"fffff {col.lower()}")
			#			indID = hed.index(col.lower().strip())
			#		elif col.lower() == 'name':
			#			indName = hed.index(col.lower())
			#		elif col.lower() == 'parent':
			#			indexparent = hed.index(col.lower())
			#		else:
			#		  	frappe.throw(msg=_("Something went wrong. One 55 or more is Missing"), title=_("Column Missing"))
			#	else:
			#		frappe.throw(msg=_(f"Something went wrong.1ssss One Column or more is Missing{col}111{col in '%id_name%'}"), title=_("Column Missing"))
			next(csvreader,None)
			for row in csvreader:
				item_list.append({'id':row[0],'name':row[1],'parent':row[2]}) 
			check_groub(item_list)


def check_groub(item_data):

		for item in item_data:
			print("face ")
			print(item)
			if not frappe.db.exists("Item Group",{'id_woocommerce':item.get('id')}) or not frappe.db.exists("Item Group",{'id_woocommerce':item.get('id')}):
				doc = frappe.get_doc(
				{
				"doctype": "Item Group",
				"name": item.get("id")+"-"+ item.get("name"),
				"item_group_name":item.get("id")+"-"+ item.get("name"),
				'id_woocommerce': item.get("id"),
				"name_woocommerce":item.get("name").lower().strip(),
				"is_groub":'1',
				}
				).insert()
				doc.save()
				frappe.db.sql(f"""UPDATE `tabItem Group` SET `is_group` = '1' WHERE `tabItem Group`.`name` = '{doc.name}';""")
			elif(frappe.db.exists("Item Group",{'id_woocommerce':item.get('id')})):
				group = frappe.get_doc("Item Group", {'id_woocommerce':item.get("id")})
				group.item_group_name = item.get("id")+"-"+ item.get("name")
				group.id_woocommerce = item.get("id")
				group.name_woocommerce = item.get("name").lower().strip()
				group.save()
		for item in item_data:
			print(item)
			category = frappe.get_doc("Item Group", {"id_woocommerce": item.get('id')})
			if (item.get('parent')!= 0 and item.get('parent')!= "0"):
				parent = frappe.get_doc("Item Group", {"id_woocommerce": item.get('parent')})
				name = parent.name
			else:
				name = "Categories"
			category.parent_item_groub= name
			category.save()
			frappe.db.sql(
			f"""
			UPDATE `tabItem Group` SET `parent_item_group` = '{name}' WHERE `tabItem Group`.`name` = '{category.name}';
			""")


	