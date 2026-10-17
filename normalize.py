"""Turns raw page text into stable text before hashing.

Step 1 only does whitespace cleanup. The noise filter (timestamps, counters,
tokens, sensitivity) is added in a later step, and it plugs in here.
"""
import hashlib
import re


def normalize(text: str) -> str:
    lines = (re.sub(r"[ \t ]+", " ", ln).strip() for ln in text.splitlines())
    return "\n".join(ln for ln in lines if ln)


def content_hash(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
