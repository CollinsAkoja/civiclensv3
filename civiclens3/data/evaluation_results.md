# CivicLens AI evaluation

Labels in `data/test_reports.csv` are a draft: review and correct them yourself, and extend the set to 150-300 reports before relying on the numbers.

## Classification: Rule-based baseline

- Reports evaluated: 60
- Accuracy: **0.65**
- Macro-F1: **0.66**

| Category | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Roads and potholes | 0.50 | 0.90 | 0.64 | 10 |
| Drainage and flooding | 0.88 | 0.70 | 0.78 | 10 |
| Waste and sanitation | 1.00 | 0.60 | 0.75 | 10 |
| Water supply | 0.86 | 0.60 | 0.71 | 10 |
| Streetlights and public facilities | 1.00 | 0.40 | 0.57 | 10 |
| Other | 0.41 | 0.70 | 0.52 | 10 |

Most common mistakes (true -> predicted):

- Water supply -> Other: 3
- Streetlights and public facilities -> Roads and potholes: 3
- Streetlights and public facilities -> Other: 3
- Drainage and flooding -> Roads and potholes: 2
- Waste and sanitation -> Other: 2
- Other -> Roads and potholes: 2

## Duplicate detection

- Labelled pairs: 20 (10 true duplicates)
- Threshold: 0.55
- Precision: **0.69**, Recall: **0.90**, F1: **0.78**
- True positives 9, false positives 4, false negatives 1, true negatives 6

Recall is favoured over precision on purpose: flags go to a human reviewer, so a false alarm costs a few seconds while a missed duplicate distorts the statistics.
Pair categories here come from the rule-based classifier, so its mistakes affect these results.

| Pair | Truth | Score | Report A | Report B |
|---|---|---|---|---|
| 1 | duplicate | 0.74 | Pothole at Dutse junction | Bad hole in the road at Dutse junction |
| 2 | duplicate | 0.70 | Blocked drain at Kubwa market | Gutter overflow near Kubwa market |
| 3 | duplicate | 0.86 | No water in Phase 2 | Borehole broken in Phase 2 |
| 4 | duplicate | 0.71 | Streetlights off on Church Road | Dark road near the church |
| 5 | duplicate | 0.70 | Waste heap at Byazhin | Refuse piling up in Byazhin |
| 6 | duplicate | 1.00 | Pothole on Airport Road, Dutse | Pothole on Airport Road Dutse |
| 7 | duplicate | 0.00 | Burst pipe at Kubwa roundabout | Water pipe leaking at roundabout |
| 8 | duplicate | 0.70 | Collapsed culvert in Dutse | Culvert fell down in Dutse |
| 9 | duplicate | 0.88 | Burning refuse near clinic | Smoke from burning rubbish by the clinic |
| 10 | duplicate | 0.91 | Broken swings in Kubwa playground | Playground in Kubwa has rusted swings |
| 11 | different | 0.00 | Pothole on Market Road, Dutse | Blocked drain on Market Road, Dutse |
| 12 | different | 0.00 | Pothole at Dutse junction | Pothole at Byazhin market |
| 13 | different | 0.00 | No water supply in Phase 2 | Refuse heap in Phase 2 |
| 14 | different | 0.58 | Streetlights off on Church Road | Garbage not collected on Church Road |
| 15 | different | 0.90 | Pothole on Airport Road, Dutse | Pothole on Airport Road Dutse |
| 16 | different | 0.00 | Burst pipe at Kubwa roundabout | Traffic light off at Kubwa roundabout |
| 17 | different | 0.00 | Streetlights off on Church Road Dutse | Streetlights off along Market Road Byazhin |
| 18 | different | 0.69 | Overflowing waste bins at estate entrance | Overflowing drain at estate entrance |
| 19 | different | 0.00 | No water supply at hostel | No water supply at the school |
| 20 | different | 0.65 | Pothole near the church | Pothole near the mosque |
