#!/usr/bin/env python3

import json

# Path to your JSONL file
jsonl_file_path = '../vector_indexes/main/embeddings.jsonl'


def mark_tokens_as_outputs(file_path):
    # Read the existing JSONL file
    updated_entries = []

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line.strip())  # Read the JSON entry

            # Check if the 'output' field exists, and mark it as True if needed
            if 'output' not in entry or not entry['output']:
                entry['output'] = True  # Mark as output if it's not already marked

            updated_entries.append(entry)

    # Write the updated entries back to the file
    with open(file_path, 'w', encoding='utf-8') as f:
        for entry in updated_entries:
            f.write(json.dumps(entry) + "\n")

    print(f"Updated {len(updated_entries)} entries to mark them as output.")


# Run the function
mark_tokens_as_outputs(jsonl_file_path)
