"""
utils/serialize_utils.py — JSON Serialization Utilities
=========================================================
Standalone serialize_doc() that converts Python objects to JSON-safe types.
No hard MongoDB/Motor/bson dependency — works with plain dicts from the
Node.js API. bson.ObjectId is imported lazily/optionally (see below) only
to stay defensive in case any raw Motor/pymongo document ever reaches this
function directly (e.g. future direct-Mongo code paths, or any leftover
caller this migration didn't touch).

Replaces: from models.finance_models import serialize_doc

✅ FIX (2026-07): the ObjectId branch below used to reference `ObjectId`
without importing it anywhere in this module — `from bson import ObjectId`
was accidentally left out of the try/except, leaving an empty `try:`
block. Since `ObjectId` was never bound in this module's scope, evaluating
`isinstance(doc, ObjectId)` always raised NameError (not ImportError), and
the `except ImportError` guard never caught it, so serialize_doc() crashed
on its very last branch for any doc that didn't match one of the earlier
isinstance checks (list/dict/datetime/date/set/bytes) — bson doesn't even
need to be installed for that final branch to be reached, since it's the
unconditional fallback at the end of the function. This surfaced loudly
once the v6.5 Node API migration routed real traffic through
serialize_doc() from endpoints like /finance/actions/log,
/finance/legal/cases, and /finance/actions/dashboard-data. Restored the
import and now also catch NameError defensively, so a genuinely
bson-less environment degrades to "return doc as-is" instead of crashing.
"""

from datetime import datetime, date


def serialize_doc(doc):
    """
    Recursively convert a document → JSON-serializable Python types.

    Handles:
        datetime  → ISO 8601 str
        date      → ISO 8601 str
        ObjectId  → str          (if bson is available, otherwise ignored)
        dict      → dict         (recursive)
        list      → list         (recursive)
        set       → list
        bytes     → str (utf-8)
        Other     → as-is        (str, int, float, bool, None)
    """
    if doc is None:
        return None

    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]

    if isinstance(doc, dict):
        result = {}
        for key, value in doc.items():
            # Skip MongoDB internal _id if it's an ObjectId
            if key == "_id":
                try:
                    result[key] = str(value)
                except Exception:
                    result[key] = value
                continue
            result[key] = serialize_doc(value)
        return result

    if isinstance(doc, datetime):
        return doc.isoformat()

    if isinstance(doc, date):
        return doc.isoformat()

    if isinstance(doc, set):
        return list(doc)

    if isinstance(doc, bytes):
        try:
            return doc.decode("utf-8")
        except Exception:
            return str(doc)

    # Try handling ObjectId if bson happens to be available.
    # ✅ FIX: the import was missing — ObjectId must be bound here before
    # isinstance() can reference it, otherwise this raises NameError (not
    # ImportError) and skips straight past the except clause below.
    try:
        from bson import ObjectId
        if isinstance(doc, ObjectId):
            return str(doc)
    except ImportError:
        # bson/pymongo not installed in this environment — nothing to do,
        # fall through and return doc as-is below.
        pass
    except NameError:
        # Defensive: should be unreachable now that the import above is
        # restored, but kept so a future accidental removal of that import
        # degrades to "return doc as-is" instead of crashing every call.
        pass

    return doc