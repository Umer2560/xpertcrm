import re
from collections import defaultdict
import frappe
from frappe import _

def extract_digits(val: str) -> str:
    """Strips all non-numeric characters from a string."""
    if not val:
        return ""
    return re.sub(r"[^\d]", "", str(val))

def get_last_n_digits(val: str, n: int) -> str:
    """Extracts the last N digits of a phone string."""
    digits = extract_digits(val)
    return digits[-n:] if len(digits) >= n else digits

def get_doctype_fields(doctype):
    """Dynamically resolves title, mobile, and email fieldnames for a given DocType."""
    meta = frappe.get_meta(doctype)
    fieldnames = [f.fieldname for f in meta.fields]
    
    title_field = meta.title_field or "name"
    if title_field not in fieldnames and title_field != "name":
        title_field = "name"
        
    mobile_field = None
    for m in ["mobile_no", "phone", "mobile", "phone_no"]:
        if m in fieldnames:
            mobile_field = m
            break
            
    email_field = None
    for e in ["email", "email_id", "email_address"]:
        if e in fieldnames:
            email_field = e
            break
            
    return title_field, mobile_field, email_field

@frappe.whitelist()
def get_duplicate_clusters(doctype="CRM Lead", match_by="mobile"):
    """
    Finds duplicate clusters for the specified DocType and filter criterion.
    - doctype: CRM Lead, Customer, Contact, CRM Deal
    - match_by: mobile, email, both
    """
    valid_doctypes = ["CRM Lead", "Customer", "Contact", "CRM Deal"]
    if doctype not in valid_doctypes:
        doctype = "CRM Lead"
        
    title_field, mobile_field, email_field = get_doctype_fields(doctype)

    clusters = []
    cluster_id_counter = 1

    fields_to_fetch = ["name", "owner", "creation"]
    if title_field and title_field != "name" and title_field not in fields_to_fetch:
        fields_to_fetch.append(title_field)
    if mobile_field and mobile_field not in fields_to_fetch:
        fields_to_fetch.append(mobile_field)
    if email_field and email_field not in fields_to_fetch:
        fields_to_fetch.append(email_field)

    # 1. MOBILE NUMBER MATCHING (2-Stage Tail Digit Matcher: 7-digits -> 10-digits)
    if match_by in ["mobile", "both"] and mobile_field:
        records = frappe.get_all(
            doctype,
            fields=fields_to_fetch,
            filters={mobile_field: ["is", "set"]}
        )
        
        # Stage 1: Group by last 7 digits candidate buckets
        seven_digit_buckets = defaultdict(list)
        for r in records:
            raw_mobile = r.get(mobile_field)
            l7 = get_last_n_digits(raw_mobile, 7)
            if len(l7) == 7:
                seven_digit_buckets[l7].append(r)
                
        # Stage 2: Verify exact match on last 10 digits
        for l7, candidate_recs in seven_digit_buckets.items():
            if len(candidate_recs) > 1:
                ten_digit_buckets = defaultdict(list)
                for r in candidate_recs:
                    l10 = get_last_n_digits(r.get(mobile_field), 10)
                    if len(l10) == 10:
                        ten_digit_buckets[l10].append(r)
                        
                for l10_key, exact_recs in ten_digit_buckets.items():
                    if len(exact_recs) > 1:
                        # Rank by creation date (oldest first) for recommended master
                        sorted_recs = sorted(exact_recs, key=lambda x: str(x.creation))
                        master_id = sorted_recs[0]["name"]
                        
                        # Add title property to records for uniform UI display
                        for rec in sorted_recs:
                            rec["display_title"] = rec.get(title_field) or rec.get("name")
                            
                        clusters.append({
                            "cluster_id": f"mob_{cluster_id_counter}",
                            "match_type": "Mobile Number",
                            "match_by": "mobile",
                            "cluster_key": l10_key,
                            "display_key": f"Last 10 Digits: {l10_key}",
                            "total_count": len(sorted_recs),
                            "recommended_master": master_id,
                            "records": sorted_recs
                        })
                        cluster_id_counter += 1

    # 2. EMAIL ADDRESS MATCHING
    if match_by in ["email", "both"] and email_field:
        email_records = frappe.get_all(
            doctype,
            fields=fields_to_fetch,
            filters={email_field: ["is", "set"]}
        )
        
        email_buckets = defaultdict(list)
        for r in email_records:
            raw_email = r.get(email_field)
            if raw_email:
                norm_email = raw_email.strip().lower()
                if norm_email:
                    email_buckets[norm_email].append(r)
                    
        for norm_email, recs in email_buckets.items():
            if len(recs) > 1:
                sorted_recs = sorted(recs, key=lambda x: str(x.creation))
                master_id = sorted_recs[0]["name"]
                
                for rec in sorted_recs:
                    rec["display_title"] = rec.get(title_field) or rec.get("name")
                    
                clusters.append({
                    "cluster_id": f"email_{cluster_id_counter}",
                    "match_type": "Email Address",
                    "match_by": "email",
                    "cluster_key": norm_email,
                    "display_key": f"Email: {norm_email}",
                    "total_count": len(sorted_recs),
                    "recommended_master": master_id,
                    "records": sorted_recs
                })
                cluster_id_counter += 1

    return {
        "doctype": doctype,
        "match_by": match_by,
        "total_clusters": len(clusters),
        "clusters": clusters
    }

@frappe.whitelist()
def merge_duplicate_records(doctype, master_doc, duplicate_docs):
    """
    Merges selected duplicate documents into the target master document.
    doctype: DocType name (e.g. CRM Lead)
    master_doc: ID of record to keep
    duplicate_docs: JSON list or comma separated string of record IDs to merge
    """
    if not frappe.has_permission(doctype, "write"):
        frappe.throw(_("Permission denied to merge {0} records.").format(doctype))
        
    if isinstance(duplicate_docs, str):
        duplicate_docs = frappe.parse_json(duplicate_docs)
        
    if not isinstance(duplicate_docs, list):
        frappe.throw(_("Invalid duplicate documents list provided."))

    merged_count = 0
    for dup_id in duplicate_docs:
        if dup_id and dup_id != master_doc:
            frappe.rename_doc(doctype, dup_id, master_doc, merge=True)
            merged_count += 1
            
    frappe.db.commit()
    
    return {
        "status": "success",
        "message": _("Successfully merged {0} duplicate record(s) into {1}").format(merged_count, master_doc),
        "master_doc": master_doc,
        "merged_count": merged_count
    }

@frappe.whitelist()
def delete_duplicate_records(doctype, docs_to_delete):
    """
    Deletes selected duplicate documents.
    doctype: DocType name (e.g. CRM Lead)
    docs_to_delete: JSON list or list of record IDs to delete
    """
    if not frappe.has_permission(doctype, "delete"):
        frappe.throw(_("Permission denied to delete {0} records.").format(doctype))
        
    if isinstance(docs_to_delete, str):
        docs_to_delete = frappe.parse_json(docs_to_delete)
        
    if not isinstance(docs_to_delete, list):
        frappe.throw(_("Invalid documents list provided for deletion."))

    deleted_count = 0
    for doc_id in docs_to_delete:
        if doc_id and frappe.db.exists(doctype, doc_id):
            frappe.delete_doc(doctype, doc_id, ignore_permissions=False)
            deleted_count += 1
            
    frappe.db.commit()
    
    return {
        "status": "success",
        "message": _("Successfully deleted {0} record(s)").format(deleted_count),
        "deleted_count": deleted_count
    }

