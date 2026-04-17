#!/usr/bin/env python3
"""
Ingestion Pipeline Runner
==========================
Runs all 3 phases of the ingestion pipeline end-to-end:
  1. Scraper  → data/cleaned_docs.jsonl
  2. Chunker  → data/chunks.jsonl
  3. Embedder → data/chroma_db/ + data/ingestion_manifest.json

Logs all activity to data/logs/scheduler_<YYYY-MM-DD>.log

Usage:
  python ingestion/run_pipeline.py
"""

from __future__ import annotations

import io
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
_ROOT = _HERE.parent

LOG_DIR = _ROOT / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
LOG_FILE = LOG_DIR / f"scheduler_{TODAY}.log"

# ── Logging Setup ─────────────────────────────────────────────────────────────
_utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# File handler + console handler
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ"
))

console_handler = logging.StreamHandler(_utf8_stdout)
console_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ"
))

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
log = logging.getLogger("pipeline")

# ── Pipeline Runner ───────────────────────────────────────────────────────────

class PipelineRunner:
    def __init__(self):
        self.start_time: float | None = None
        self.stats: dict[str, Any] = {
            "scrape": {"urls_total": 0, "urls_ok": 0, "urls_failed": 0, "details": []},
            "chunk": {"docs_in": 0, "chunks_out": 0, "total_tokens": 0},
            "embed": {"new": 0, "updated": 0, "unchanged": 0, "deleted": 0, "upserted": 0},
        }
        self.errors: list[str] = []

    def log_section(self, title: str) -> None:
        log.info("=" * 68)
        log.info(title)
        log.info("=" * 68)

    def run_scraper(self) -> bool:
        self.log_section("PHASE 1: SCRAPING")
        
        urls_yaml = _ROOT / "data" / "urls.yaml"
        output_jsonl = _ROOT / "data" / "cleaned_docs.jsonl"
        raw_dir = _ROOT / "data" / "raw"
        
        # Count URLs
        try:
            import yaml
            with open(urls_yaml, "r", encoding="utf-8") as f:
                urls_data = yaml.safe_load(f)
                url_list = urls_data.get("urls", [])
                self.stats["scrape"]["urls_total"] = len(url_list)
                log.info(f"Found {len(url_list)} URLs to scrape")
        except Exception as e:
            log.error(f"Failed to read urls.yaml: {e}")
            self.errors.append(f"urls.yaml read error: {e}")
            return False
        
        # Run scraper
        env = os.environ.copy()
        env.update({
            "URLS_YAML": str(urls_yaml),
            "OUTPUT_JSONL": str(output_jsonl),
            "RAW_DIR": str(raw_dir),
        })
        
        log.info("Starting scraper...")
        t0 = time.time()
        
        try:
            result = subprocess.run(
                [sys.executable, str(_HERE / "scraper.py")],
                cwd=str(_ROOT),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            elapsed = time.time() - t0
            log.info(f"Scraper completed in {elapsed:.1f}s (exit code: {result.returncode})")
            
            # Parse output for individual URL status
            if result.stdout:
                for line in result.stdout.split("\n"):
                    if " Mirae Asset" in line or "scheme" in line.lower():
                        log.info(f"  [SCRAPE] {line.strip()}")
                    if "error" in line.lower() or "failed" in line.lower():
                        self.stats["scrape"]["urls_failed"] += 1
                        log.warning(f"  [SCRAPE ERROR] {line.strip()}")
            
            if result.stderr:
                for line in result.stderr.split("\n")[:20]:  # Limit stderr logging
                    if line.strip():
                        log.warning(f"  [SCRAPE STDERR] {line.strip()}")
            
            # Count results
            if output_jsonl.exists():
                with open(output_jsonl, "r", encoding="utf-8") as f:
                    lines = [l for l in f if l.strip()]
                    self.stats["scrape"]["urls_ok"] = len(lines)
                    
                    # Log each URL scraped
                    for line in lines:
                        try:
                            doc = json.loads(line)
                            url = doc.get("source_url", "unknown")
                            status = doc.get("status", "unknown")
                            scheme = doc.get("scheme_name", "unknown")
                            self.stats["scrape"]["details"].append({
                                "url": url,
                                "scheme": scheme,
                                "status": status
                            })
                            log.info(f"  Scraped: {scheme} ({status})")
                        except json.JSONDecodeError:
                            pass
                
                failed = self.stats["scrape"]["urls_total"] - self.stats["scrape"]["urls_ok"]
                self.stats["scrape"]["urls_failed"] = failed
                log.info(f"Scraper stats: {self.stats['scrape']['urls_ok']} OK, {failed} failed")
            
            return result.returncode == 0
            
        except Exception as e:
            log.error(f"Scraper failed with exception: {e}")
            self.errors.append(f"Scraper exception: {e}")
            return False

    def run_chunker(self) -> bool:
        self.log_section("PHASE 2: CHUNKING")
        
        input_jsonl = _ROOT / "data" / "cleaned_docs.jsonl"
        output_jsonl = _ROOT / "data" / "chunks.jsonl"
        
        env = os.environ.copy()
        env.update({
            "INPUT_JSONL": str(input_jsonl),
            "OUTPUT_JSONL": str(output_jsonl),
            "PIPELINE_RUN_ID": f"local-{TODAY}",
        })
        
        log.info("Starting chunker...")
        t0 = time.time()
        
        try:
            result = subprocess.run(
                [sys.executable, str(_HERE / "chunker.py")],
                cwd=str(_ROOT),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            elapsed = time.time() - t0
            log.info(f"Chunker completed in {elapsed:.1f}s (exit code: {result.returncode})")
            
            # Parse stats from stdout
            docs_in = 0
            chunks_out = 0
            total_tokens = 0
            
            if result.stdout:
                for line in result.stdout.split("\n"):
                    line_lower = line.lower()
                    if "document" in line_lower and ("processed" in line_lower or "read" in line_lower):
                        log.info(f"  [CHUNK] {line.strip()}")
                        # Try to extract numbers
                        import re
                        nums = re.findall(r'\d+', line)
                        if nums:
                            docs_in = int(nums[0])
                    if "chunk" in line_lower and ("wrote" in line_lower or "created" in line_lower):
                        log.info(f"  [CHUNK] {line.strip()}")
                        import re
                        nums = re.findall(r'\d+', line)
                        if nums:
                            chunks_out = int(nums[0])
            
            # Count actual output
            if output_jsonl.exists():
                with open(output_jsonl, "r", encoding="utf-8") as f:
                    lines = [l for l in f if l.strip()]
                    chunks_out = len(lines)
                    
                    # Count tokens and docs
                    doc_hashes = set()
                    for line in lines:
                        try:
                            chunk = json.loads(line)
                            doc_hashes.add(chunk.get("doc_hash", ""))
                            self.stats["chunk"]["total_tokens"] += chunk.get("token_count", 0)
                        except json.JSONDecodeError:
                            pass
                    
                    docs_in = len(doc_hashes)
            
            self.stats["chunk"]["docs_in"] = docs_in
            self.stats["chunk"]["chunks_out"] = chunks_out
            
            log.info(f"Chunker stats: {docs_in} docs → {chunks_out} chunks, {self.stats['chunk']['total_tokens']} total tokens")
            
            return result.returncode == 0
            
        except Exception as e:
            log.error(f"Chunker failed with exception: {e}")
            self.errors.append(f"Chunker exception: {e}")
            return False

    def run_embedder(self) -> bool:
        self.log_section("PHASE 3: EMBEDDING & UPSERT")
        
        chunks_jsonl = _ROOT / "data" / "chunks.jsonl"
        manifest_path = _ROOT / "data" / "ingestion_manifest.json"
        chroma_path = _ROOT / "data" / "chroma_db"
        
        env = os.environ.copy()
        env.update({
            "CHUNKS_JSONL": str(chunks_jsonl),
            "MANIFEST_PATH": str(manifest_path),
            "CHROMA_PERSIST_PATH": str(chroma_path),
            "PIPELINE_RUN_ID": f"local-{TODAY}",
            "FORCE_FULL_RERUN": "false",
        })
        
        log.info("Starting embedder...")
        t0 = time.time()
        
        try:
            result = subprocess.run(
                [sys.executable, str(_HERE / "embedder.py")],
                cwd=str(_ROOT),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            elapsed = time.time() - t0
            log.info(f"Embedder completed in {elapsed:.1f}s (exit code: {result.returncode})")
            
            # Parse stats from stdout
            if result.stdout:
                for line in result.stdout.split("\n"):
                    line_lower = line.lower()
                    if any(x in line_lower for x in ["new", "updated", "unchanged", "deleted", "embed", "upsert"]):
                        log.info(f"  [EMBED] {line.strip()}")
                        
                        # Extract counts
                        import re
                        nums = re.findall(r'\d+', line)
                        if nums:
                            if "new" in line_lower:
                                self.stats["embed"]["new"] = int(nums[0])
                            elif "updated" in line_lower:
                                self.stats["embed"]["updated"] = int(nums[0])
                            elif "unchanged" in line_lower:
                                self.stats["embed"]["unchanged"] = int(nums[0])
                            elif "deleted" in line_lower:
                                self.stats["embed"]["deleted"] = int(nums[0])
                            elif "upsert" in line_lower:
                                self.stats["embed"]["upserted"] = int(nums[0])
            
            # Read manifest for stats
            if manifest_path.exists():
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                        entries = manifest.get("entries", [])
                        
                        new_count = sum(1 for e in entries if e.get("status") == "NEW")
                        updated_count = sum(1 for e in entries if e.get("status") == "UPDATED")
                        unchanged_count = sum(1 for e in entries if e.get("status") == "UNCHANGED")
                        deleted_count = sum(1 for e in entries if e.get("status") == "DELETED")
                        
                        self.stats["embed"]["new"] = new_count
                        self.stats["embed"]["updated"] = updated_count
                        self.stats["embed"]["unchanged"] = unchanged_count
                        self.stats["embed"]["deleted"] = deleted_count
                        self.stats["embed"]["upserted"] = new_count + updated_count
                        
                        log.info(f"Manifest stats: {len(entries)} total entries")
                        log.info(f"  NEW: {new_count}, UPDATED: {updated_count}, UNCHANGED: {unchanged_count}, DELETED: {deleted_count}")
                except Exception as e:
                    log.warning(f"Could not parse manifest: {e}")
            
            log.info(f"Embedder stats: {self.stats['embed']['new']} new, {self.stats['embed']['updated']} updated, "
                     f"{self.stats['embed']['unchanged']} unchanged, {self.stats['embed']['deleted']} deleted, "
                     f"{self.stats['embed']['upserted']} upserted to ChromaDB")
            
            return result.returncode == 0
            
        except Exception as e:
            log.error(f"Embedder failed with exception: {e}")
            self.errors.append(f"Embedder exception: {e}")
            return False

    def run(self) -> bool:
        self.start_time = time.time()
        
        self.log_section("INGESTION PIPELINE START")
        log.info(f"Start time: {datetime.now(timezone.utc).isoformat()}")
        log.info(f"Log file: {LOG_FILE}")
        log.info(f"Working directory: {_ROOT}")
        
        success = True
        
        # Phase 1: Scraper
        if not self.run_scraper():
            log.error("Scraper phase failed")
            success = False
        
        # Phase 2: Chunker (only if scraper produced output)
        cleaned_docs = _ROOT / "data" / "cleaned_docs.jsonl"
        if cleaned_docs.exists() and cleaned_docs.stat().st_size > 0:
            if not self.run_chunker():
                log.error("Chunker phase failed")
                success = False
        else:
            log.error("No cleaned_docs.jsonl found, skipping chunker")
            success = False
        
        # Phase 3: Embedder (only if chunker produced output)
        chunks_jsonl = _ROOT / "data" / "chunks.jsonl"
        if chunks_jsonl.exists() and chunks_jsonl.stat().st_size > 0:
            if not self.run_embedder():
                log.error("Embedder phase failed")
                success = False
        else:
            log.error("No chunks.jsonl found, skipping embedder")
            success = False
        
        # Summary
        total_time = time.time() - self.start_time
        self.print_summary(total_time, success)
        
        return success

    def print_summary(self, total_time: float, success: bool) -> None:
        self.log_section("PIPELINE SUMMARY")
        
        log.info(f"Total execution time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
        log.info(f"Overall status: {'SUCCESS' if success else 'FAILED'}")
        
        log.info("")
        log.info("SCRAPER STATS:")
        log.info(f"  Total URLs: {self.stats['scrape']['urls_total']}")
        log.info(f"  Successful: {self.stats['scrape']['urls_ok']}")
        log.info(f"  Failed: {self.stats['scrape']['urls_failed']}")
        
        log.info("")
        log.info("CHUNKER STATS:")
        log.info(f"  Documents in: {self.stats['chunk']['docs_in']}")
        log.info(f"  Chunks out: {self.stats['chunk']['chunks_out']}")
        log.info(f"  Total tokens: {self.stats['chunk']['total_tokens']}")
        avg_tokens = self.stats['chunk']['total_tokens'] / max(self.stats['chunk']['chunks_out'], 1)
        log.info(f"  Avg tokens/chunk: {avg_tokens:.0f}")
        
        log.info("")
        log.info("EMBEDDER STATS:")
        log.info(f"  NEW chunks: {self.stats['embed']['new']}")
        log.info(f"  UPDATED chunks: {self.stats['embed']['updated']}")
        log.info(f"  UNCHANGED chunks: {self.stats['embed']['unchanged']}")
        log.info(f"  DELETED chunks: {self.stats['embed']['deleted']}")
        log.info(f"  Total upserted to ChromaDB: {self.stats['embed']['upserted']}")
        
        if self.errors:
            log.info("")
            log.info("ERRORS:")
            for err in self.errors:
                log.error(f"  - {err}")
        
        log.info("")
        log.info(f"Log written to: {LOG_FILE}")
        log.info("=" * 68)


def main() -> None:
    runner = PipelineRunner()
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
