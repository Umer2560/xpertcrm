import io
import os
import json
import base64
import hashlib
import logging
from datetime import datetime
from typing import Optional, Dict, Any

import frappe
from frappe.utils import cint, flt, getdate, now_datetime

# Optional dependencies
try:
    from PIL import Image, ImageEnhance

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from groq import Groq

    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False


# CONFIGURATION
class PaymentProofAIConfig:

    # Groq vision model
    MODEL = "qwen/qwen3.6-27b"

    # Image processing
    MAX_IMAGE_WIDTH = 1200
    JPEG_QUALITY = 65

    # AI
    TEMPERATURE = 0
    MAX_COMPLETION_TOKENS = 2048

    # Processing
    MAX_IMAGE_SIZE_MB = 20

    # Deal fields
    PAYMENT_PROOF_FIELD = "custom_payment_proof"

    PAID_AMOUNT_FIELD = "custom_paid_amount"
    PAYMENT_DATE_FIELD = "custom_payment_date"
    TRANSACTION_ID_FIELD = "custom_reference_number"

    AI_STATUS_FIELD = "custom_payment_ai_status"
    AI_ERROR_FIELD = "custom_payment_ai_error"
    AI_PROCESSED_FIELD = "custom_payment_ai_processed"
    AI_HASH_FIELD = "custom_payment_ai_processed_hash"


# LOGGING
logger = logging.getLogger("crm_payment_proof_ai")

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s | payment_proof_ai | %(levelname)s | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

logger.setLevel(logging.INFO)


# SYSTEM PROMPT
PAYMENT_EXTRACTION_SYSTEM_PROMPT = """
    You are a payment receipt data extraction engine.

    Your ONLY task is to extract payment information visible in the
    supplied payment proof image.

    CRITICAL: Respond IMMEDIATELY with ONLY the raw JSON object. Do NOT output any thinking, reasoning, explanation, or <think> tags.

    Extract exactly these fields:

    1. paid_amount
    2. payment_date
    3. transaction_id

    STRICT RULES:

    - Extract only information that is visibly present in the image.
    - NEVER guess, infer, calculate, fabricate, or reconstruct missing values.
    - If a value cannot be clearly identified, return null.
    - paid_amount must be a numeric amount without currency symbols or commas.
    - payment_date must use YYYY-MM-DD format when the date is clearly identifiable.
    - If the date is ambiguous or cannot be confidently converted to
    YYYY-MM-DD, return null.
    - transaction_id must contain the transaction/reference/trace ID
    exactly as visible.
    - Do not confuse account numbers, phone numbers, invoice numbers,
    customer IDs, order IDs, or other numbers with transaction_id.
    - Prefer labels such as:
    "Transaction ID",
    "Transaction No",
    "Transaction Number",
    "Reference Number",
    "Reference ID",
    "Trace ID",
    "RRN",
    "UTR",
    "Payment ID".
    - If multiple transaction/reference numbers exist, select the one
    most clearly associated with the payment transaction.
    - Do not extract unrelated amounts such as account balance,
    available balance, fees, taxes, discounts, or invoice totals
    unless they are clearly the paid amount.
    - If multiple payment amounts are displayed, identify the amount
    explicitly associated with the completed payment.
    - Return ONLY valid JSON.
    - Do not include explanations.
    - Do not include markdown.

    Required JSON format:

    {
        "paid_amount": null,
        "payment_date": null,
        "transaction_id": null
    }
"""


# ANALYZER
class PaymentProofAnalyzer:

    def __init__(self):
        self.logger = logger

    # Public API

    def process_deal(self, deal_name: str) -> Dict[str, Any]:
        try:
            if not deal_name:
                return self._fail("CRM Deal name is required.")

            if not frappe.db.exists("CRM Deal", deal_name):
                return self._fail(f"CRM Deal {deal_name} does not exist.")

            deal = frappe.get_doc("CRM Deal", deal_name)
            try:
                deal.reload()
            except Exception:
                pass
            return self.process_deal_doc(deal)
        except Exception as e:
            self.logger.exception("Payment proof processing failed")
            self._set_failed_status(deal_name, str(e))
            return {"status": "failed", "error": str(e)}

    def process_deal_doc(self, doc) -> Dict[str, Any]:
        try:
            print("\n--------------------------------------------------")
            print(f"[AI_ANALYTICS] Starting process_deal_doc for deal: {getattr(doc, 'name', 'New Deal')}")

            if not doc:
                print("[AI_ANALYTICS] ERROR: CRM Deal doc is None.")
                return self._fail("CRM Deal doc is required.")

            payment_proof = doc.get(PaymentProofAIConfig.PAYMENT_PROOF_FIELD)
            print(f"[AI_ANALYTICS] Attachment field ({PaymentProofAIConfig.PAYMENT_PROOF_FIELD}): {payment_proof}")

            if not payment_proof:
                print("[AI_ANALYTICS] SKIPPED: No payment proof attached.")
                return {"status": "skipped", "reason": "No payment proof attached."}

            file_doc = self._get_file(payment_proof)
            print(f"[AI_ANALYTICS] Resolved File document: {file_doc}")
            image_bytes = None

            if file_doc:
                image_bytes = self._read_file(file_doc)
            else:
                rel_path = payment_proof.lstrip("/")
                possible_paths = [
                    frappe.get_site_path("public", "files", os.path.basename(rel_path)),
                    frappe.get_site_path("private", "files", os.path.basename(rel_path)),
                    frappe.get_site_path("public", rel_path),
                    frappe.get_site_path("private", rel_path),
                    frappe.get_site_path(rel_path),
                ]
                print(f"[AI_ANALYTICS] Attempting file path resolution from possible locations...")
                for p in possible_paths:
                    if os.path.exists(p):
                        try:
                            print(f"[AI_ANALYTICS] Found image file on disk at: {p}")
                            with open(p, "rb") as f:
                                image_bytes = f.read()
                            break
                        except Exception as file_err:
                            print(f"[AI_ANALYTICS] Failed reading path {p}: {file_err}")

            if not image_bytes:
                print(f"[AI_ANALYTICS] FAILED: Unable to read image bytes for file {payment_proof}")
                return self._fail(f"Unable to read payment proof file: {payment_proof}")

            print(f"[AI_ANALYTICS] Read {len(image_bytes)} image bytes successfully.")

            if len(image_bytes) > (PaymentProofAIConfig.MAX_IMAGE_SIZE_MB * 1024 * 1024):
                print("[AI_ANALYTICS] FAILED: Image size exceeds maximum allowed limit.")
                return self._fail("Payment proof image exceeds maximum allowed size.")

            image_base64 = self._preprocess_image(image_bytes)
            if not image_base64:
                print("[AI_ANALYTICS] FAILED: Image preprocessing failed.")
                return self._fail("Unable to preprocess payment proof image.")

            print("[AI_ANALYTICS] Calling Groq AI Vision model...")
            extracted = self._extract_with_groq(image_base64)
            print(f"[AI_ANALYTICS] Groq AI Vision raw extraction result: {extracted}")

            if not extracted:
                print("[AI_ANALYTICS] FAILED: AI could not extract payment information.")
                return self._fail("AI could not extract payment information.")

            normalized = self._validate_extracted_data(extracted)
            print(f"[AI_ANALYTICS] Normalized AI Data: {normalized}")

            if not normalized:
                print("[AI_ANALYTICS] FAILED: Normalized AI data is empty/invalid.")
                return self._fail("AI returned invalid payment information.")

            # Set extracted values directly on the doc
            if normalized.get("paid_amount") is not None:
                doc.custom_paid_amount = normalized.get("paid_amount")
                print(f"[AI_ANALYTICS] Set doc.custom_paid_amount = {normalized.get('paid_amount')}")

            if normalized.get("payment_date") is not None:
                doc.custom_payment_date = normalized.get("payment_date")
                print(f"[AI_ANALYTICS] Set doc.custom_payment_date = {normalized.get('payment_date')}")

            if normalized.get("transaction_id") is not None:
                tx_id = normalized.get("transaction_id")
                meta_fields = [f.fieldname for f in doc.meta.fields] if hasattr(doc, "meta") else []
                if "custom_reference_number" in meta_fields or hasattr(doc, "custom_reference_number"):
                    doc.custom_reference_number = tx_id
                if "custom_transaction_id" in meta_fields or hasattr(doc, "custom_transaction_id"):
                    doc.custom_transaction_id = tx_id
                doc.set("custom_reference_number", tx_id)
                print(f"[AI_ANALYTICS] Set doc.custom_reference_number = {tx_id}")

            file_hash = hashlib.sha256(image_bytes).hexdigest()
            meta = frappe.get_meta("CRM Deal")
            valid_fields = {f.fieldname for f in meta.fields}

            if PaymentProofAIConfig.AI_STATUS_FIELD in valid_fields:
                doc.set(PaymentProofAIConfig.AI_STATUS_FIELD, "Completed")
            if PaymentProofAIConfig.AI_ERROR_FIELD in valid_fields:
                doc.set(PaymentProofAIConfig.AI_ERROR_FIELD, "")
            if PaymentProofAIConfig.AI_PROCESSED_FIELD in valid_fields:
                doc.set(PaymentProofAIConfig.AI_PROCESSED_FIELD, "1")
            if PaymentProofAIConfig.AI_HASH_FIELD in valid_fields:
                doc.set(PaymentProofAIConfig.AI_HASH_FIELD, file_hash)

            deal_name = getattr(doc, "name", None)
            if deal_name and frappe.db.exists("CRM Deal", deal_name):
                self._update_deal(deal_name, normalized, file_hash)

            print(f"[AI_ANALYTICS] SUCCESS: Payment proof processing completed for deal {deal_name or 'New'}")
            print("--------------------------------------------------\n")

            return {
                "status": "success",
                "paid_amount": normalized.get("paid_amount"),
                "payment_date": normalized.get("payment_date"),
                "transaction_id": normalized.get("transaction_id"),
            }

        except Exception as e:
            print(f"[AI_ANALYTICS] EXCEPTION in process_deal_doc: {e}")
            self.logger.exception("Payment proof processing failed in process_deal_doc")
            deal_name = getattr(doc, "name", None)
            if deal_name:
                self._set_failed_status(deal_name, str(e))
            return {"status": "failed", "error": str(e)}

    # File handling

    def _get_file(self, file_url: str):
        try:
            file_doc = frappe.db.get_value(
                "File",
                {"file_url": file_url},
                ["name", "file_name", "file_url", "is_private"],
                as_dict=True,
            )
            if file_doc:
                return frappe.get_doc("File", file_doc.name)

            alt_url = "/" + file_url.lstrip("/")
            file_doc = frappe.db.get_value(
                "File",
                {"file_url": alt_url},
                ["name", "file_name", "file_url", "is_private"],
                as_dict=True,
            )
            if file_doc:
                return frappe.get_doc("File", file_doc.name)

            file_name = file_url.split("/")[-1]
            file_doc = frappe.db.get_value(
                "File",
                {"file_name": file_name},
                ["name", "file_name", "file_url", "is_private"],
                as_dict=True,
            )
            if file_doc:
                return frappe.get_doc("File", file_doc.name)

        except Exception:
            self.logger.exception("Could not resolve file: %s", file_url)

        return None

    def _read_file(self, file_doc) -> Optional[bytes]:
        try:
            if hasattr(file_doc, "get_full_path"):
                file_path = file_doc.get_full_path()
            else:
                rel_path = file_doc.file_url.lstrip("/")
                if getattr(file_doc, "is_private", 0):
                    file_path = frappe.get_site_path(
                        "private", "files", os.path.basename(rel_path)
                    )
                else:
                    file_path = frappe.get_site_path(
                        "public", "files", os.path.basename(rel_path)
                    )

            if not os.path.exists(file_path):
                alt_path = frappe.get_site_path(file_doc.file_url.lstrip("/"))
                if os.path.exists(alt_path):
                    file_path = alt_path
                else:
                    self.logger.error("File does not exist at path: %s", file_path)
                    return None

            with open(file_path, "rb") as f:
                return f.read()

        except Exception:
            self.logger.exception("Failed reading payment proof file.")
            return None

    # Image preprocessing

    def _preprocess_image(self, image_bytes: bytes) -> Optional[str]:
        if not HAS_PIL:
            self.logger.info("Pillow not installed, encoding raw image bytes directly.")
            return base64.b64encode(image_bytes).decode("utf-8")

        try:
            image = Image.open(io.BytesIO(image_bytes))

            # Fix EXIF orientation
            try:
                from PIL import ImageOps

                image = ImageOps.exif_transpose(image)
            except Exception:
                pass

            # Convert supported formats to RGB
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")

            if image.mode == "L":
                image = image.convert("RGB")

            # Resize
            if image.width > PaymentProofAIConfig.MAX_IMAGE_WIDTH:
                ratio = PaymentProofAIConfig.MAX_IMAGE_WIDTH / image.width
                new_height = int(image.height * ratio)
                image = image.resize(
                    (PaymentProofAIConfig.MAX_IMAGE_WIDTH, new_height), Image.LANCZOS
                )

            # Mild contrast enhancement
            try:
                image = ImageEnhance.Contrast(image).enhance(1.05)
            except Exception:
                pass

            # JPEG compression
            buffer = io.BytesIO()
            image.save(
                buffer,
                format="JPEG",
                quality=PaymentProofAIConfig.JPEG_QUALITY,
                optimize=True,
            )

            compressed = buffer.getvalue()

            self.logger.info(
                "Image compressed: %s KB -> %s KB",
                round(len(image_bytes) / 1024, 2),
                round(len(compressed) / 1024, 2),
            )

            return base64.b64encode(compressed).decode("utf-8")

        except Exception:
            self.logger.exception("Image preprocessing failed, fallback to raw encoding.")
            return base64.b64encode(image_bytes).decode("utf-8")

    # Hash

    def _calculate_file_hash(self, file_doc) -> str:
        content = self._read_file(file_doc)
        if not content:
            return ""
        return hashlib.sha256(content).hexdigest()

    # Groq

    def _get_groq_api_key(self) -> Optional[str]:
        try:
            for key_name in [
                "GROQ_API_KEY",
                "groq_api_key",
                "groq_key",
                "groq_api_token",
            ]:
                key = frappe.conf.get(key_name)
                if key:
                    return key
        except Exception:
            pass

        return os.environ.get("GROQ_API_KEY")

    def _extract_with_groq(self, image_base64: str) -> Optional[Dict]:
        api_key = self._get_groq_api_key()
        print(f"[GROQ_DEBUG] API Key present: {bool(api_key)}")
        if not api_key:
            print("[GROQ_DEBUG] ERROR: Groq API key is not configured in site_config or environment.")
            self.logger.error("Groq API key is not configured in site_config or environment.")
            return None

        # 1. Try Groq SDK if installed
        if HAS_GROQ:
            try:
                print(f"[GROQ_DEBUG] Attempting Groq SDK call with model {PaymentProofAIConfig.MODEL}...")
                client = Groq(api_key=api_key)
                messages = [
                    {"role": "system", "content": PAYMENT_EXTRACTION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract the payment information from this payment proof image in valid JSON format.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                },
                            },
                        ],
                    },
                ]

                completion = client.chat.completions.create(
                    model=PaymentProofAIConfig.MODEL,
                    messages=messages,
                    temperature=PaymentProofAIConfig.TEMPERATURE,
                    max_completion_tokens=PaymentProofAIConfig.MAX_COMPLETION_TOKENS,
                    response_format={"type": "json_object"},
                    reasoning_effort="none",
                    stream=False,
                )

                raw_content = completion.choices[0].message.content
                print(f"[GROQ_DEBUG] SDK raw completion content: {raw_content}")
                if raw_content:
                    parsed = self._parse_json_response(raw_content)
                    if parsed:
                        return parsed
            except Exception as e:
                print(f"[GROQ_DEBUG] Groq SDK call exception (falling back to HTTP): {e}")
                self.logger.warning(f"Groq SDK call failed, using HTTP fallback: {e}")

        # 2. HTTP Request Fallback (Dependency-free with Retry & Fallback)
        try:
            import requests
            import time

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            payload_base = {
                "model": PaymentProofAIConfig.MODEL,
                "messages": [
                    {"role": "system", "content": PAYMENT_EXTRACTION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract the payment information from this payment proof image in valid JSON format.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                },
                            },
                        ],
                    },
                ],
                "temperature": PaymentProofAIConfig.TEMPERATURE,
                "max_completion_tokens": PaymentProofAIConfig.MAX_COMPLETION_TOKENS,
            }

            # Attempt 1: strictly requested json_object response format
            payload = dict(payload_base)
            payload["response_format"] = {"type": "json_object"}

            print(f"[GROQ_DEBUG] Sending HTTP POST to Groq API (model={PaymentProofAIConfig.MODEL})...")
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )

            print(f"[GROQ_DEBUG] Groq HTTP Response Status Code: {response.status_code}")

            # If rate limited (429), sleep 3 seconds and retry once
            if response.status_code == 429:
                print("[GROQ_DEBUG] Rate limit hit (429). Sleeping 3s before retry...")
                time.sleep(3)
                response = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60,
                )
                print(f"[GROQ_DEBUG] Retry Groq HTTP Response Status Code: {response.status_code}")

            # If HTTP 400 (e.g. json_validate_failed error), fallback without response_format constraint
            if response.status_code == 400 and "json_validate_failed" in response.text:
                print("[GROQ_DEBUG] json_validate_failed detected. Retrying without strict response_format constraint...")
                response = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload_base,
                    timeout=60,
                )
                print(f"[GROQ_DEBUG] Fallback HTTP Response Status Code: {response.status_code}")

            if response.status_code != 200:
                print(f"[GROQ_DEBUG] ERROR: Groq HTTP Response ({response.status_code}): {response.text}")
                self.logger.error("Groq API HTTP error (%s): %s", response.status_code, response.text)
                return None

            res_json = response.json()
            raw_content = res_json.get("choices", [{}])[0].get("message", {}).get("content")
            print(f"[GROQ_DEBUG] HTTP raw completion content: {raw_content}")

            if not raw_content:
                print("[GROQ_DEBUG] FAILED: Raw content in choices message is empty.")
                return None

            return self._parse_json_response(raw_content)

        except Exception as http_err:
            print(f"[GROQ_DEBUG] HTTP request Exception: {http_err}")
            self.logger.exception("Groq extraction via HTTP request failed.")
            return None

    def _parse_json_response(self, raw_content: str) -> Optional[Dict]:
        print(f"[PARSE_DEBUG] Parsing raw AI content: {raw_content}")
        if not raw_content:
            return None

        import re

        # Clean reasoning <think>...</think> tags if present
        if "<think>" in raw_content:
            if "</think>" in raw_content:
                raw_content = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL).strip()
            else:
                raw_content = re.sub(r"^<think>.*?(?=\{)", "", raw_content, flags=re.DOTALL).strip()
            print(f"[PARSE_DEBUG] Content after removing <think> tags: {raw_content}")

        # Extract JSON from markdown code blocks
        if "```" in raw_content:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_content, re.DOTALL)
            if match:
                raw_content = match.group(1).strip()
                print(f"[PARSE_DEBUG] Content after extracting code block: {raw_content}")

        try:
            parsed = json.loads(raw_content)
            print(f"[PARSE_DEBUG] Successfully parsed JSON dictionary: {parsed}")
            return parsed
        except json.JSONDecodeError:
            json_match = re.search(r"(\{[\s\S]*\})", raw_content)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(1))
                    print(f"[PARSE_DEBUG] Successfully parsed JSON dictionary via regex extraction: {parsed}")
                    return parsed
                except json.JSONDecodeError as err:
                    print(f"[PARSE_DEBUG] JSONDecodeError on regex extract: {err}")

            print(f"[PARSE_DEBUG] Could not parse JSON from content: {raw_content}")
            self.logger.error("Groq returned invalid JSON: %s", raw_content)
            return None

    # Validation

    def _validate_extracted_data(self, data: Dict) -> Optional[Dict]:

        if not isinstance(data, dict):
            return None

        paid_amount = data.get("paid_amount")
        payment_date = data.get("payment_date")
        transaction_id = data.get("transaction_id")

        # Amount
        normalized_amount = None
        if paid_amount is not None:
            try:
                if isinstance(paid_amount, str):
                    cleaned = (
                        paid_amount.replace(",", "")
                        .replace("PKR", "")
                        .replace("Rs.", "")
                        .replace("Rs", "")
                        .replace("$", "")
                        .strip()
                    )
                    normalized_amount = flt(cleaned)
                else:
                    normalized_amount = flt(paid_amount)

                if normalized_amount <= 0:
                    normalized_amount = None
            except Exception:
                normalized_amount = None

        # Date
        normalized_date = None
        if payment_date:
            try:
                normalized_date = getdate(payment_date)
            except Exception:
                normalized_date = None

        # Transaction ID / Reference Number
        normalized_transaction_id = None
        if transaction_id:
            transaction_id = str(transaction_id).strip()
            if transaction_id and transaction_id.lower() != "null":
                normalized_transaction_id = transaction_id

        # At least one useful field should be extracted
        if (
            normalized_amount is None
            and normalized_date is None
            and normalized_transaction_id is None
        ):
            return None

        return {
            "paid_amount": normalized_amount,
            "payment_date": normalized_date,
            "transaction_id": normalized_transaction_id,
        }

    # Deal updates

    def _set_processing_status(self, deal_name: str, file_hash: str):
        try:
            meta = frappe.get_meta("CRM Deal")
            valid_fields = {f.fieldname for f in meta.fields}
            values = {}

            if PaymentProofAIConfig.AI_STATUS_FIELD in valid_fields:
                values[PaymentProofAIConfig.AI_STATUS_FIELD] = "Processing"
            if PaymentProofAIConfig.AI_ERROR_FIELD in valid_fields:
                values[PaymentProofAIConfig.AI_ERROR_FIELD] = ""
            if PaymentProofAIConfig.AI_HASH_FIELD in valid_fields:
                values[PaymentProofAIConfig.AI_HASH_FIELD] = file_hash

            if values:
                frappe.db.set_value("CRM Deal", deal_name, values, update_modified=False)
        except Exception:
            self.logger.exception("Unable to set processing status.")

    def _update_deal(self, deal_name: str, data: Dict, file_hash: str):
        meta = frappe.get_meta("CRM Deal")
        valid_fields = {f.fieldname for f in meta.fields}

        values = {}

        if "custom_paid_amount" in valid_fields and data.get("paid_amount") is not None:
            values["custom_paid_amount"] = data.get("paid_amount")

        if "custom_payment_date" in valid_fields and data.get("payment_date") is not None:
            values["custom_payment_date"] = data.get("payment_date")

        if "custom_reference_number" in valid_fields and data.get("transaction_id") is not None:
            values["custom_reference_number"] = data.get("transaction_id")

        if "custom_transaction_id" in valid_fields and data.get("transaction_id") is not None:
            values["custom_transaction_id"] = data.get("transaction_id")

        # Tracking fields if available
        tracking_map = {
            PaymentProofAIConfig.AI_STATUS_FIELD: "Completed",
            PaymentProofAIConfig.AI_ERROR_FIELD: "",
            PaymentProofAIConfig.AI_PROCESSED_FIELD: "1",
            PaymentProofAIConfig.AI_HASH_FIELD: file_hash,
        }

        for fld, val in tracking_map.items():
            if fld in valid_fields:
                values[fld] = val

        if values:
            frappe.db.set_value("CRM Deal", deal_name, values, update_modified=True)

        try:
            frappe.publish_realtime(
                "crm_deal_payment_proof_processed",
                {"deal_name": deal_name, "extracted": data},
            )
        except Exception:
            pass

    def _set_failed_status(self, deal_name: str, error: str):
        if not deal_name:
            return

        try:
            meta = frappe.get_meta("CRM Deal")
            valid_fields = {f.fieldname for f in meta.fields}
            values = {}

            if PaymentProofAIConfig.AI_STATUS_FIELD in valid_fields:
                values[PaymentProofAIConfig.AI_STATUS_FIELD] = "Failed"
            if PaymentProofAIConfig.AI_ERROR_FIELD in valid_fields:
                values[PaymentProofAIConfig.AI_ERROR_FIELD] = str(error)[:500]

            if values:
                frappe.db.set_value("CRM Deal", deal_name, values, update_modified=False)
                frappe.db.commit()

        except Exception:
            self.logger.exception("Unable to update failed status.")

    def _fail(self, message: str) -> Dict:
        self.logger.error(message)
        return {"status": "failed", "error": message}


# GLOBAL INSTANCE
payment_proof_analyzer = PaymentProofAnalyzer()


# WHITELISTED API
@frappe.whitelist()
def analyze_payment_proof(deal_name: str) -> Dict:
    if not deal_name:
        return {"status": "failed", "error": "deal_name is required."}

    return payment_proof_analyzer.process_deal(deal_name)


# BACKGROUND WORKER
def payment_proof_worker(deal_name: str):
    try:
        return payment_proof_analyzer.process_deal(deal_name)
    except Exception as e:
        logger.exception("Payment proof background worker failed.")
        return {"status": "failed", "error": str(e)}


# DOCUMENT HOOKS
def on_crm_deal_save(doc, method=None):
    """
    Hook called when CRM Deal is saved (after_insert or on_update).
    If custom_payment_proof is attached, enqueue AI processing.
    """
    payment_proof = doc.get(PaymentProofAIConfig.PAYMENT_PROOF_FIELD)

    if not payment_proof:
        return

    previous_doc = None
    try:
        previous_doc = doc.get_doc_before_save()
    except Exception:
        pass

    previous_payment_proof = (
        previous_doc.get(PaymentProofAIConfig.PAYMENT_PROOF_FIELD)
        if previous_doc
        else None
    )

    is_new_or_changed = payment_proof != previous_payment_proof
    is_unprocessed = not doc.get(PaymentProofAIConfig.AI_PROCESSED_FIELD) and not (
        doc.get(PaymentProofAIConfig.PAID_AMOUNT_FIELD)
        and doc.get(PaymentProofAIConfig.PAYMENT_DATE_FIELD)
    )

    if is_new_or_changed or is_unprocessed:
        frappe.enqueue(
            "xpertintegration.api.ai_analytics.payment_proof_worker",
            queue="short",
            timeout=300,
            deal_name=doc.name,
            now=getattr(frappe.flags, "in_test", False),
        )


def on_crm_deal_after_save(doc, method=None):
    """Alias for on_crm_deal_save."""
    on_crm_deal_save(doc, method=method)
