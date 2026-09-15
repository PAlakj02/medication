# Ingredient Resolution Coverage Report

Generated against **10,907 canonical ingredients** and **1,001 aliases** currently loaded in the DB.

Read-only report — re-resolves each source's raw names against the current ingredient/alias state, does not modify the DB or `data/aliases.csv`.

## 1. Unresolved ingredient names per source

### DDInter

- Total mentions: 320,470
- Resolved: 275,984 (86.1%)
- Unresolved: 44,486 (386 distinct names)
- Resolution breakdown: exact=260,133, sy=3,271, normalized=10,715, curated=0

Top 30 unresolved names (by mention count):

| Name | Mentions |
|---|---|
| Sibutramine | 570 |
| Alimemazine | 562 |
| Tolbutamide | 461 |
| Picosulfuric acid | 459 |
| Chlorpropamide | 449 |
| Indacaterol | 438 |
| Dicoumarol | 433 |
| Troglitazone | 422 |
| Tolazamide | 419 |
| Ethinylestradiol | 409 |
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
| Saquinavir | 312 |
| Alefacept | 307 |
| Telithromycin | 305 |
| Insulin aspart (aspart protamine) | 303 |

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
- Resolved: 291,658 (82.1%)
- Unresolved: 63,730 (561 distinct names)
- Resolution breakdown: exact=253,020, sy=2,333, normalized=1,038, curated=7,319

## 2. DDInter ATC category coverage

**Caveat**: DDInter's bulk CSV export carries no ATC code column, and the RxNorm RXNCONSO.RRF in this data drop has zero ATC-sourced rows — there is no real per-ingredient ATC mapping available in this pipeline to compute this precisely. The signal below is which of DDInter's per-category download files are present (their single-letter names match WHO ATC top-level codes) — an approximate proxy for category coverage, not a verified per-drug ATC mapping.

**Present** (8/14): A (Alimentary tract and metabolism), B (Blood and blood forming organs), D (Dermatologicals), H (Systemic hormonal preparations, excl. sex hormones), L (Antineoplastic and immunomodulating agents), P (Antiparasitic products, insecticides and repellents), R (Respiratory system), V (Various)

**Missing** (6/14): C (Cardiovascular system), G (Genito-urinary system and sex hormones), J (Antiinfectives for systemic use), M (Musculoskeletal system), N (Nervous system), S (Sensory organs)

Check DDInter's download page for these category files — if they exist upstream and simply weren't downloaded, that's the single highest-leverage gap to close (whole anatomical categories with zero interaction coverage).

## 3. Indian medicine dataset: product-level resolution

- Total non-discontinued products with at least one parseable composition: 246,068
- Fully resolved (every listed ingredient matches a known ingredient): 185,223 (75.3%)
- Partially or fully unresolved (at least one ingredient did not match): 60,845 (24.7%)

## 4. Top 50 unresolved India ingredient names — work queue for `data/aliases.csv`

Ranked by number of distinct products each name appears in — highest-impact first. For each, check: is this a genuine alias for an existing ingredient (add to `data/aliases.csv`), a salt-form spelling `normalize_salt_form` should already catch but doesn't (extend the salt-form list), or a real ingredient RxNorm doesn't have at all (nothing to alias — it's a legitimately new ingredient)?

| Rank | Name | Product count |
|---|---|---|
| 1 | Aceclofenac | 9,000 |
| 2 | Domperidone | 8,898 |
| 3 | Nimesulide | 3,299 |
| 4 | Ornidazole | 3,287 |
| 5 | Thiocolchicoside | 2,080 |
| 6 | Etoricoxib | 1,979 |
| 7 | Levosulpiride | 1,722 |
| 8 | Lactobacillus | 1,470 |
| 9 | Nandrolone Decanoate | 1,469 |
| 10 | Cefoperazone | 1,328 |
| 11 | Drotaverine | 1,235 |
| 12 | Voglibose | 1,058 |
| 13 | Trypsin | 1,028 |
| 14 | Betahistine | 1,006 |
| 15 | Tricholine Citrate | 921 |
| 16 | Cilnidipine | 871 |
| 17 | Teneligliptin | 858 |
| 18 | Vildagliptin | 837 |
| 19 | Ursodeoxycholic Acid | 793 |
| 20 | Piracetam | 780 |
| 21 | Gliclazide | 778 |
| 22 | Cloxacillin | 709 |
| 23 | Diacerein | 694 |
| 24 | Oxetacaine | 676 |
| 25 | Acebrophylline | 607 |
| 26 | Roxithromycin | 596 |
| 27 | Norfloxacin | 512 |
| 28 | Etizolam | 510 |
| 29 | Flunarizine | 473 |
| 30 | Lornoxicam | 440 |
| 31 | Cinnarizine | 423 |
| 32 | Itopride | 409 |
| 33 | Alpha-Beta Arteether | 387 |
| 34 | Vitamin D3 | 349 |
| 35 | Thyroxine | 317 |
| 36 | Doxofylline | 314 |
| 37 | Phenylpropanolamine | 305 |
| 38 | Fusidic Acid | 300 |
| 39 | Sparfloxacin | 264 |
| 40 | Hydroxyprogesterone | 252 |
| 41 | Bilastine | 237 |
| 42 | Norethisterone | 237 |
| 43 | Flupenthixol | 228 |
| 44 | Trypsin Chymotrypsin | 212 |
| 45 | Arteether | 203 |
| 46 | L-Ornithine L-Aspartate | 201 |
| 47 | Tolperisone | 200 |
| 48 | Nicotinamide | 188 |
| 49 | Cetrimide | 179 |
| 50 | Hydroxypropylmethylcellulose | 156 |

