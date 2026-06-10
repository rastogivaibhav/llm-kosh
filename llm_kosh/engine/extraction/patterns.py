"""Compiled regex patterns for legal causal extraction."""
from typing import List, Tuple

# Pattern type name -> EdgeType string value
PATTERN_TO_EDGE_TYPE = {
    "CITES": "ENABLES",
    "OVERRULES": "SUPERSEDES",
    "INTERPRETS": "ENABLES",
    "APPLIES": "ENABLES",
    "DISTINGUISHES": "CONTRASTS",
    "CAUSES": "CAUSES",
    "SUPERSEDES": "SUPERSEDES",
}

CITES_PATTERNS: List[str] = [
    r'\[See\s+(?P<case>[A-Z][^,\]]+),?\s*(?P<citation>\(\d{4}\)\s*\d+\s*SCC\s*\d+)\]',
    r'(?:as held in|relied upon|following|in accordance with|as laid down in|as observed in)\s+(?P<case>[A-Z][^\(,\.]+(?:v\.|vs\.|versus)[^\(,\.]+),?\s*(?P<citation>(?:AIR\s+\d{4}|(?:\(\d{4}\)\s*\d+\s*SCC))[\s\w]+)',
    r'(?P<case>[A-Z][^\(]+(?:v\.|vs\.|versus)[^\(]+)\s*reported in\s+(?P<citation>(?:AIR\s+\d{4}|\(\d{4}\)\s*\d+\s*SCC)[\s\d\w]+)',
    r'(?P<case>[A-Z][^\(]+(?:v\.|vs\.|versus)[^\(]+)\s*\(supra\)',
    r'(?P<case>[A-Z][^\(]*(?:v\.|vs\.|versus)[^\(]*)\s*\((?P<citation>(?:19|20)\d{2})\)\s*\d+\s+(?:SCC|SCR|ELT|Scale|AIR)\s+\d+',
]

OVERRULES_PATTERNS: List[str] = [
    r'(?:is|are|therefore|hereby)\s+overruled',
    r'overruling\s+(?:the|our)?\s*(?:earlier|previous|prior)?\s*(?:decision|judgment|order)',
    r'no longer\s+(?:good|valid)\s+law',
    r'cannot be treated as good law',
]

INTERPRETS_PATTERNS: List[str] = [
    r'(?:Section|Article|Rule|Clause)\s+\d+[\w\(\)]*\s+(?:of\s+the\s+[\w\s]+Act)?[\s,]+(?:means|provides|states|reads|requires|contemplates|mandates|provides for)',
    r'A reading of\s+(?:Section|Article)\s+\d+[\w\(\)]*',
    r'(?:interpreting|interpretation of)\s+(?:Section|Article)\s+\d+',
    r'under the provisions? of\s+(?:Section|Article)\s+\d+',
]

APPLIES_PATTERNS: List[str] = [
    r'(?:Applying|applying)\s+(?:the\s+)?(?:principle|ratio|test|doctrine|law|rule)\s+(?:in|from|of|laid down in)\s+',
    r'(?:In view of|In terms of|In light of)\s+(?:the\s+)?(?:judgment|decision|ruling|order)\s+in\s+',
    r'(?:following|adopting)\s+(?:the\s+)?(?:ratio|principle|test|view)\s+(?:in|of)',
]

DISTINGUISHES_PATTERNS: List[str] = [
    r'facts?\s+(?:of\s+(?:the\s+)?(?:present|this|instant)\s+case\s+)?(?:are\s+)?clearly\s+distinguishable',
    r'distinguished?\s+from\s+(?:\w[^\.\n]+)',
    r'unlike\s+(?:the\s+)?(?:case|facts)\s+in\s+(?:[A-Z][^\.\n]+)',
    r'the present case is different from',
]

CAUSES_PATTERNS: List[str] = [
    r'(?:pursuant to|consequent(?:ly)?(?:\s+upon)?|as a result of|resulting in|which led to|leading to)\s+',
    r'(?:gave rise to|led to)\s+(?:the\s+)?(?:filing|registration|institution|commencement)\s+of',
    r'(?:aggrieved by|feeling aggrieved)\s+.*(?:filed|preferred)\s+(?:an?\s+)?(?:appeal|petition|application)',
]

SUPERSEDES_PATTERNS: List[str] = [
    r'(?:stands?\s+repealed|is\s+repealed)\s+and\s+(?:is\s+)?replaced by',
    r'(?:supersedes?|replaces?)\s+(?:the\s+)?(?:earlier|previous|prior)\s+',
    r'(?:earlier|previous)\s+(?:decision|order|Act)\s+is\s+no longer\s+(?:good|valid)\s+law',
]

# Ordered list for extract_facts_and_edges: (pattern_type, patterns, base_confidence)
PATTERN_LIST: List[Tuple[str, List[str], float]] = [
    ("OVERRULES",     OVERRULES_PATTERNS,     0.90),
    ("CITES",         CITES_PATTERNS,         0.85),
    ("SUPERSEDES",    SUPERSEDES_PATTERNS,    0.80),
    ("INTERPRETS",    INTERPRETS_PATTERNS,    0.75),
    ("APPLIES",       APPLIES_PATTERNS,       0.70),
    ("DISTINGUISHES", DISTINGUISHES_PATTERNS, 0.70),
    ("CAUSES",        CAUSES_PATTERNS,        0.65),
]
