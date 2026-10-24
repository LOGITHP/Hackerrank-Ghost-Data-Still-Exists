"""Parser and indexer for multi-modal participant evidence files.
Supports JSON, SQL, LOG, TXT, PDF, and OCR for images.
"""

import glob
import json
import os
import re
from typing import Any, Dict, List, Optional, Set
import pandas as pd


class EvidenceRecord:
    """Represents a discovered resource or record inside an evidence file."""

    def __init__(
        self,
        evidence_id: str,
        system_id: str,
        resource_id: str,
        captured_dt: Optional[pd.Timestamp],
        user_references: Set[str],
        data: Dict[str, Any],
        raw_text: str = "",
    ):
        self.evidence_id = evidence_id
        self.system_id = system_id
        self.resource_id = resource_id
        self.captured_dt = captured_dt
        self.user_references = {u.lower() for u in user_references if u}
        self.data = data
        self.raw_text = raw_text

    def matches_user(self, identifiers: Set[str]) -> bool:
        """Check if any user identifier appears in the record's references or text."""
        norm_ids = {i.lower() for i in identifiers if i}
        if self.user_references.intersection(norm_ids):
            return True
        for ident in norm_ids:
            if len(ident) >= 4 and ident in self.raw_text.lower():
                return True
        return False


class EvidenceStore:
    """In-memory cache and index for all admissible evidence records."""

    def __init__(self, manifest_df: pd.DataFrame, base_dir: str = "."):
        self.manifest_df = manifest_df
        self.base_dir = base_dir
        self.records: List[EvidenceRecord] = []
        self.records_by_resource: Dict[str, List[EvidenceRecord]] = {}
        self.records_by_evidence_id: Dict[str, List[EvidenceRecord]] = {}
        self.raw_evidence_texts: Dict[str, str] = {}
        self._parsed = False

    def load_all_evidence(self):
        """Parse all files listed in manifest."""
        if self._parsed:
            return

        for _, row in self.manifest_df.iterrows():
            ev_id = str(row.get("evidence_id") or row.get("file_id") or "")
            rel_path = str(row["file_path"])
            full_path = os.path.join(self.base_dir, rel_path) if not os.path.isabs(rel_path) else rel_path
            file_type = str(row.get("file_type", "")).lower()
            sys_id = str(row.get("system_id", ""))
            captured_at = row.get("captured_at")
            captured_dt = pd.to_datetime(captured_at) if pd.notna(captured_at) else None

            if not os.path.exists(full_path):
                continue

            try:
                if "json" in file_type or full_path.endswith(".json"):
                    self._parse_json_file(ev_id, sys_id, full_path, captured_dt)
                elif "sql" in file_type or full_path.endswith(".sql"):
                    self._parse_sql_file(ev_id, sys_id, full_path, captured_dt)
                elif "log" in file_type or full_path.endswith(".log"):
                    self._parse_log_file(ev_id, sys_id, full_path, captured_dt)
                elif "text" in file_type or full_path.endswith(".txt"):
                    self._parse_text_file(ev_id, sys_id, full_path, captured_dt)
                elif "pdf" in file_type or full_path.endswith(".pdf"):
                    self._parse_pdf_file(ev_id, sys_id, full_path, captured_dt)
                elif "image" in file_type or full_path.endswith((".png", ".jpg", ".jpeg")):
                    self._parse_image_file(ev_id, sys_id, full_path, captured_dt)
            except Exception as e:
                # Log parsing error and continue
                pass

        # Build lookup indexes
        for rec in self.records:
            if rec.resource_id not in self.records_by_resource:
                self.records_by_resource[rec.resource_id] = []
            self.records_by_resource[rec.resource_id].append(rec)

            if rec.evidence_id not in self.records_by_evidence_id:
                self.records_by_evidence_id[rec.evidence_id] = []
            self.records_by_evidence_id[rec.evidence_id].append(rec)

        self._parsed = True

    def _parse_json_file(self, ev_id: str, default_sys: str, path: str, captured_dt: Optional[pd.Timestamp]):
        with open(path, "r", encoding="utf-8", errors="ignore") as fp:
            raw_text = fp.read()
        self.raw_evidence_texts[ev_id] = raw_text

        try:
            data = json.loads(raw_text)
        except Exception:
            return

        def walk(obj, parent_sys=default_sys):
            if isinstance(obj, dict):
                rid = obj.get("resource_id") or obj.get("id")
                sys_id = obj.get("system_id") or obj.get("service") or obj.get("data_store") or parent_sys

                # Extract user references
                refs = set()
                for key in ["user_id", "customer_reference", "subject_reference", "subject_selector", "email", "phone", "requester_email"]:
                    val = obj.get(key)
                    if val and isinstance(val, str):
                        refs.add(val)

                if rid and isinstance(rid, str) and ("_" in rid or rid.startswith(("acc", "res", "tomb", "data", "back", "supp", "sec", "audit"))):
                    rec = EvidenceRecord(
                        evidence_id=ev_id,
                        system_id=sys_id,
                        resource_id=rid,
                        captured_dt=captured_dt,
                        user_references=refs,
                        data=obj,
                        raw_text=json.dumps(obj),
                    )
                    self.records.append(rec)

                for k, v in obj.items():
                    walk(v, sys_id)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item, parent_sys)

        walk(data)

    def _parse_sql_file(self, ev_id: str, default_sys: str, path: str, captured_dt: Optional[pd.Timestamp]):
        with open(path, "r", encoding="utf-8", errors="ignore") as fp:
            content = fp.read()
        self.raw_evidence_texts[ev_id] = content

        # Process INSERT INTO lines
        for line in content.splitlines():
            if not line.startswith("INSERT INTO"):
                continue

            tbl_match = re.search(r"INSERT INTO\s+[\"']?(\w+)[\"']?", line)
            table_name = tbl_match.group(1) if tbl_match else ""

            # Check JSON blob in table
            match_json = re.search(r"VALUES\s*\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'({.+})'", line)
            if match_json:
                rid, sys_id, tbl, json_str = match_json.groups()
                try:
                    obj = json.loads(json_str)
                except Exception:
                    obj = {"raw": json_str}

                refs = set()
                for k in ["user_id", "customer_reference", "subject_reference", "email", "phone", "customer_email"]:
                    val = obj.get(k)
                    if val and isinstance(val, str):
                        refs.add(val)

                rec = EvidenceRecord(
                    evidence_id=ev_id,
                    system_id=sys_id or default_sys,
                    resource_id=rid,
                    captured_dt=captured_dt,
                    user_references=refs,
                    data=obj,
                    raw_text=line,
                )
                self.records.append(rec)
                continue

            # Standard SQL tuple: VALUES (...)
            val_match = re.search(r"VALUES\s*\((.*)\)\s*;?", line, re.DOTALL)
            if not val_match:
                continue

            val_str = val_match.group(1).strip()
            # Split by comma respecting quotes
            parts = [p.strip().strip("'\"") for p in re.split(r",\s*(?=(?:[^']*'[^']*')*[^']*$)", val_str)]
            if not parts:
                continue

            # Extract resource_id
            rid = None
            for p in parts:
                if re.match(r"^(?:account|analytics|support|search|data_flow|backup|tombstone|export|audit_record)_[0-9a-fA-F]+$", p):
                    rid = p
                    break

            if not rid:
                continue

            # Extract user references (emails, user_id, hashes)
            refs = set()
            for p in parts:
                if re.match(r"^user_\w+$", p) or "@" in p or (len(p) == 64 and re.match(r"^[0-9a-fA-F]+$", p)):
                    refs.add(p)

            # Determine system_id and state properties based on table
            sys_id = default_sys
            data: Dict[str, Any] = {"table": table_name, "values": parts}

            if "backup" in table_name or "backup" in rid:
                sys_id = "backup_service"
                # Check for restore_allowed boolean or '1'/'0'
                for p in parts:
                    if p.lower() in ["1", "true"]:
                        data["restore_allowed"] = True
                    elif p.lower() in ["0", "false"]:
                        data["restore_allowed"] = False

            elif "connector" in table_name or "data_flow" in rid:
                sys_id = "integration_service"
                for p in parts:
                    if p.lower() in ["1", "true"]:
                        data["enabled"] = True
                    elif p.lower() in ["0", "false"]:
                        data["enabled"] = False

            elif "profile" in table_name or "account" in rid:
                sys_id = "account_service"
                data["is_present"] = True

            elif "search" in table_name or "search" in rid:
                sys_id = "search_service"
                data["is_present"] = True

            elif "support" in table_name or "support" in rid:
                sys_id = "support_platform"

            elif "export" in table_name or "export" in rid:
                sys_id = "export_service"
                data["is_present"] = True

            elif "audit" in table_name or "audit_record" in rid or "security" in table_name:
                sys_id = "security_service"
                data["is_present"] = True

            rec = EvidenceRecord(
                evidence_id=ev_id,
                system_id=sys_id,
                resource_id=rid,
                captured_dt=captured_dt,
                user_references=refs,
                data=data,
                raw_text=line,
            )
            self.records.append(rec)

    def _parse_log_file(self, ev_id: str, default_sys: str, path: str, captured_dt: Optional[pd.Timestamp]):
        with open(path, "r", encoding="utf-8", errors="ignore") as fp:
            lines = fp.readlines()
        self.raw_evidence_texts[ev_id] = "".join(lines[:1000])

        # Group lines by trace_id or requestId
        traces: Dict[str, List[str]] = {}
        standalone_lines: List[str] = []

        for line in lines:
            line_str = line.strip()
            tr_match = re.search(r"\b(?:trace_id|requestId)=([^\s,\"]+)", line_str)
            if tr_match:
                tr_id = tr_match.group(1)
                if tr_id not in traces:
                    traces[tr_id] = []
                traces[tr_id].append(line_str)
            else:
                standalone_lines.append(line_str)

        # Process trace groups
        for tr_id, tr_lines in traces.items():
            combined_text = "\n".join(tr_lines)
            rids = re.findall(r"\b((?:account|analytics|support|search|data_flow|backup|tombstone|export|audit_record)_[0-9a-fA-F]+)\b", combined_text)
            uids = re.findall(r"\b(user_\w+|[\w\.-]+@[\w\.-]+\.\w+)\b", combined_text)
            hashes = re.findall(r"\b([0-9a-fA-F]{64})\b", combined_text)
            refs = set(uids).union(set(hashes))

            for rid in set(rids):
                rec = EvidenceRecord(
                    evidence_id=ev_id,
                    system_id=default_sys,
                    resource_id=rid,
                    captured_dt=captured_dt,
                    user_references=refs,
                    data={"trace_id": tr_id, "combined_lines": tr_lines},
                    raw_text=combined_text,
                )
                self.records.append(rec)

        # Process standalone lines
        for line_str in standalone_lines:
            rid_match = re.search(r"\b((?:account|analytics|support|search|data_flow|backup|tombstone|export|audit_record)_[0-9a-fA-F]+)\b", line_str)
            if rid_match:
                rid = rid_match.group(1)
                uids = re.findall(r"\b(user_\w+|[\w\.-]+@[\w\.-]+\.\w+)\b", line_str)
                rec = EvidenceRecord(
                    evidence_id=ev_id,
                    system_id=default_sys,
                    resource_id=rid,
                    captured_dt=captured_dt,
                    user_references=set(uids),
                    data={"log_line": line_str},
                    raw_text=line_str,
                )
                self.records.append(rec)

    def _parse_text_file(self, ev_id: str, default_sys: str, path: str, captured_dt: Optional[pd.Timestamp]):
        with open(path, "r", encoding="utf-8", errors="ignore") as fp:
            text = fp.read()
        self.raw_evidence_texts[ev_id] = text
        self._extract_document_records(ev_id, default_sys, text, captured_dt)

    def _parse_pdf_file(self, ev_id: str, default_sys: str, path: str, captured_dt: Optional[pd.Timestamp]):
        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
            self.raw_evidence_texts[ev_id] = full_text
            self._extract_document_records(ev_id, default_sys, full_text, captured_dt)
        except Exception:
            pass

    def _parse_image_file(self, ev_id: str, default_sys: str, path: str, captured_dt: Optional[pd.Timestamp]):
        try:
            # Singleton OCR
            if not hasattr(self, "_ocr_engine"):
                from rapidocr_onnxruntime import RapidOCR
                self._ocr_engine = RapidOCR()
            result, _ = self._ocr_engine(path)
            if result:
                text = "\n".join(line[1] for line in result)
                self.raw_evidence_texts[ev_id] = text
                self._extract_document_records(ev_id, default_sys, text, captured_dt)
        except Exception:
            pass

    def _extract_document_records(self, ev_id: str, default_sys: str, text: str, captured_dt: Optional[pd.Timestamp]):
        rids = re.findall(r"\b((?:account|analytics|support|search|data_flow|backup|tombstone|export|audit_record)_[0-9a-fA-F]+)\b", text)
        uids = re.findall(r"\b(user_\w+|[\w\.-]+@[\w\.-]+\.\w+)\b", text)
        refs = set(uids)

        for rid in set(rids):
            rec = EvidenceRecord(
                evidence_id=ev_id,
                system_id=default_sys,
                resource_id=rid,
                captured_dt=captured_dt,
                user_references=refs,
                data={"document_text": text[:500]},
                raw_text=text,
            )
            self.records.append(rec)
