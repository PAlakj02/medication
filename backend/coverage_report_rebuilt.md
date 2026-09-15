# Ingredient Resolution Coverage Report

Generated against **11,083 canonical ingredients** and **997 aliases** currently loaded in the DB.

Read-only report — re-resolves each source's raw names against the current ingredient/alias state, does not modify the DB or `data/aliases.csv`.

## 1. Unresolved ingredient names per source

### DDInter

- Total mentions: 320,470
- Resolved: 267,096 (83.3%)
- Unresolved: 53,374 (534 distinct names)
- Resolution breakdown: exact=260,133, sy=3,271, normalized=1,827, curated=0

Top 30 unresolved names (by mention count):

| Name | Mentions |
|---|---|
| Sibutramine | 570 |
| Alimemazine | 562 |
| Doxepin (topical) | 516 |
| Tolbutamide | 461 |
| Picosulfuric acid | 459 |
| Chlorpropamide | 449 |
| Indacaterol | 438 |
| Dicoumarol | 433 |
| Troglitazone | 422 |
| Tolazamide | 419 |
| Ethinylestradiol | 409 |
| Doxorubicin (liposomal) | 406 |
| Somatotropin | 405 |
| Methdilazine | 401 |
| Thiethylperazine | 396 |
| Asparaginase Escherichia coli | 395 |
| Mepyramine | 381 |
| Somatrem | 379 |
| Insulin human (inhalation, rapid acting) | 375 |
| Polyethylene glycol (3350 with electrolytes) | 374 |
| Orciprenaline | 373 |
| Isoprenaline | 364 |
| Acetohexamide | 360 |
| Insulin aspart (aspart) | 354 |
| Insulin human (isophane) | 353 |
| Insulin human (zinc) | 353 |
| Insulin human (regular) | 352 |
| Insulin human (zinc extended) | 352 |
| Brimonidine (ophthalmic) | 344 |
| Brimonidine (topical) | 344 |

### RxNorm (SBD branded products)

- Total mentions: 10,739
- Resolved: 8,219 (76.5%)
- Unresolved: 2,520 (1,308 distinct names)
- Resolution breakdown: exact=8,219, sy=0, normalized=0, curated=0

Top 30 unresolved names (by mention count):

| Name | Mentions |
|---|---|
| Streptococcus pneumoniae serotype | 64 |
| Streptococcus pneumoniae type | 44 |
| 24 HR diltiazem hydrochloride | 43 |
| 84 HR estradiol | 25 |
| 0.5 ML tirzepatide | 24 |
| Abuse-Deterrent | 19 |
| L1 protein, human papillomavirus type | 16 |
| 60 ACTUAT fluticasone propionate | 15 |
| 24 HR methylphenidate hydrochloride | 15 |
| 50 ML albumin human, USP | 14 |
| 50 ML immunoglobulin G, human | 14 |
| 100 ML immunoglobulin G, human | 12 |
| 2.4 ML tirzepatide | 12 |
| 24 HR minocycline | 11 |
| 24 HR metformin hydrochloride | 11 |
| 30 ML bupivacaine hydrochloride | 11 |
| 0.5 ML Bordetella pertussis filamentous hemagglutinin vaccine, inactivated | 11 |
| 24 HR amphetamine | 11 |
| 100 ML albumin human, USP | 11 |
| 0.25 ML somatropin | 10 |
| 10 ML bupivacaine hydrochloride | 10 |
| 200 ML immunoglobulin G, human | 10 |
| Sensor | 10 |
| 1 ML epoetin alfa | 9 |
| 12 HR carbamazepine | 9 |
| 0.4 ML methotrexate | 9 |
| 168 HR estradiol | 8 |
| 20 ML baclofen | 8 |
| 24 HR metoprolol succinate | 8 |
| 24 HR dexmethylphenidate hydrochloride | 8 |

### Indian medicine dataset

- Total mentions: 355,388
- Resolved: 284,285 (80.0%)
- Unresolved: 71,103 (568 distinct names)
- Resolution breakdown: exact=253,020, sy=2,333, normalized=984, curated=0

## 2. DDInter ATC category coverage

**Caveat**: DDInter's bulk CSV export carries no ATC code column, and the RxNorm RXNCONSO.RRF in this data drop has zero ATC-sourced rows — there is no real per-ingredient ATC mapping available in this pipeline to compute this precisely. The signal below is which of DDInter's per-category download files are present (their single-letter names match WHO ATC top-level codes) — an approximate proxy for category coverage, not a verified per-drug ATC mapping.

**Present** (8/14): A (Alimentary tract and metabolism), B (Blood and blood forming organs), D (Dermatologicals), H (Systemic hormonal preparations, excl. sex hormones), L (Antineoplastic and immunomodulating agents), P (Antiparasitic products, insecticides and repellents), R (Respiratory system), V (Various)

**Missing** (6/14): C (Cardiovascular system), G (Genito-urinary system and sex hormones), J (Antiinfectives for systemic use), M (Musculoskeletal system), N (Nervous system), S (Sensory organs)

Check DDInter's download page for these category files — if they exist upstream and simply weren't downloaded, that's the single highest-leverage gap to close (whole anatomical categories with zero interaction coverage).

## 3. Indian medicine dataset: product-level resolution

- Total non-discontinued products with at least one parseable composition: 246,068
- Fully resolved (every listed ingredient matches a known ingredient): 179,011 (72.7%)
- Partially or fully unresolved (at least one ingredient did not match): 67,057 (27.3%)

## 4. Top 50 unresolved India ingredient names — work queue for `data/aliases.csv`

Ranked by number of distinct products each name appears in — highest-impact first. For each, check: is this a genuine alias for an existing ingredient (add to `data/aliases.csv`), a salt-form spelling `normalize_salt_form` should already catch but doesn't (extend the salt-form list), or a real ingredient RxNorm doesn't have at all (nothing to alias — it's a legitimately new ingredient)?

| Rank | Name | Product count |
|---|---|---|
| 1 | Aceclofenac | 9,000 |
| 2 | Domperidone | 8,898 |
| 3 | Methylcobalamin | 3,981 |
| 4 | Nimesulide | 3,299 |
| 5 | Ornidazole | 3,287 |
| 6 | Thiocolchicoside | 2,080 |
| 7 | Tazobactum | 2,065 |
| 8 | Etoricoxib | 1,979 |
| 9 | Levosulpiride | 1,722 |
| 10 | Lactobacillus | 1,470 |
| 11 | Nandrolone Decanoate | 1,469 |
| 12 | Cefoperazone | 1,328 |
| 13 | Drotaverine | 1,235 |
| 14 | Voglibose | 1,058 |
| 15 | Trypsin | 1,028 |
| 16 | Bromelain | 1,008 |
| 17 | Betahistine | 1,006 |
| 18 | Tricholine Citrate | 921 |
| 19 | Cilnidipine | 871 |
| 20 | Teneligliptin | 858 |
| 21 | Vildagliptin | 837 |
| 22 | Ursodeoxycholic Acid | 793 |
| 23 | Piracetam | 780 |
| 24 | Gliclazide | 778 |
| 25 | Cloxacillin | 709 |
| 26 | Diacerein | 694 |
| 27 | Oxetacaine | 676 |
| 28 | Acebrophylline | 607 |
| 29 | Roxithromycin | 596 |
| 30 | Norfloxacin | 512 |
| 31 | Etizolam | 510 |
| 32 | Flunarizine | 473 |
| 33 | Lornoxicam | 440 |
| 34 | Cinnarizine | 423 |
| 35 | Itopride | 409 |
| 36 | Alpha-Beta Arteether | 387 |
| 37 | Vitamin D3 | 349 |
| 38 | Thyroxine | 317 |
| 39 | Doxofylline | 314 |
| 40 | Phenylpropanolamine | 305 |
| 41 | Fusidic Acid | 300 |
| 42 | Paracetamol/Acetaminophen | 265 |
| 43 | Sparfloxacin | 264 |
| 44 | Hydroxyprogesterone | 252 |
| 45 | Bilastine | 237 |
| 46 | Norethisterone | 237 |
| 47 | Flupenthixol | 228 |
| 48 | Trypsin Chymotrypsin | 212 |
| 49 | Arteether | 203 |
| 50 | L-Ornithine L-Aspartate | 201 |

