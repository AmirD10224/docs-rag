<!--
Repair prompt, used when the first synthesis pass produces JSON that
fails validation OR cites a chunk_id we never sent it. We give the
model the original output and the specific complaint, and ask for a
corrected JSON object. One retry only; further failures bubble up.
-->

# System

You produced an output that failed validation. Read the validator's
complaint and emit a corrected JSON object that satisfies the
`SynthesisOutput` schema. Do not add commentary. JSON only.

# User

ORIGINAL_OUTPUT:
{{original}}

VALIDATION_ERROR:
{{error}}

VALID_CHUNK_IDS:
{{valid_ids}}

QUESTION:
{{question}}

CONTEXT:
{{context_json}}

Return ONE JSON object only.
