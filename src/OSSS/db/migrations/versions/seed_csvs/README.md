✔ Step 1 — Create the FK validation output file

Run:

python seed_csvs/validate_fk_csvs.py > fk_validation_output.txt

✔ Step 2 — Build manual FK map

Run:

./build_manual_fk_map.py fk_validation_output.txt > manual_fk_map.py
