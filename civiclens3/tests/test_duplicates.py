from core.dataset import load_duplicate_pairs
from core.duplicates import THRESHOLD, find_duplicates, tokenize
from core.fallback import classify_by_rules
from core.metrics import binary_prf


def rep(rid, title, desc, community="Dutse", date="2026-09-01", category=None, **extra):
    row = dict(id=rid, title=title, description=desc, state="FCT (Abuja)", lga="Bwari",
               community=community, date_observed=date, ai_category=category)
    row.update(extra)
    return row


def test_same_problem_in_different_words_is_flagged():
    old = rep(1, "Pothole at Dutse junction", "Big pothole near the filling station damaging cars.", category="Roads and potholes")
    new = rep(2, "Bad hole in the road", "A huge hole in the tarmac near the filling station is destroying tyres.",
              date="2026-09-03", category="Roads and potholes")
    matches = find_duplicates(new, [old])
    assert [m.other_id for m in matches] == [1]
    assert "Same community" in matches[0].reasons


def test_similar_wording_but_different_issue_is_not_flagged():
    old = rep(1, "Pothole on Market Road", "A deep pothole on Market Road is damaging cars.", category="Roads and potholes")
    new = rep(2, "Blocked drain on Market Road", "The drain on Market Road is blocked and floods the road.",
              category="Drainage and flooding")
    assert find_duplicates(new, [old]) == []


def test_reports_in_other_lgas_are_never_compared():
    old = rep(1, "Pothole on Market Road", "A deep pothole on Market Road.", category="Roads and potholes")
    new = rep(2, "Pothole on Market Road", "A deep pothole on Market Road.", category="Roads and potholes")
    new["lga"] = "Kuje"
    assert find_duplicates(new, [old]) == []


def test_a_report_is_not_compared_with_itself():
    only = rep(1, "Pothole", "A deep pothole on Market Road.")
    assert find_duplicates(only, [only]) == []


def test_close_coordinates_raise_the_score():
    base = dict(category="Roads and potholes")
    old = rep(1, "Pothole near market", "Deep pothole near the market entrance.", community="A", **base,
              latitude=9.0760, longitude=7.3990)
    near = rep(2, "Hole in road by market", "Large hole in the road close to the market gate.", community="B",
               date="2026-09-02", **base, latitude=9.0762, longitude=7.3991)
    far = dict(near, latitude=9.5, longitude=7.9)
    near_matches = find_duplicates(near, [old], threshold=0.0)
    far_matches = find_duplicates(far, [old], threshold=0.0)
    assert near_matches[0].score > far_matches[0].score
    assert "Coordinates within 300 m" in near_matches[0].reasons


def test_old_reports_score_lower_than_recent_ones():
    old = rep(1, "Pothole near market", "Deep pothole near the market.", category="Roads and potholes", date="2026-01-01")
    recent = rep(2, "Pothole near market", "Deep pothole near the market.", category="Roads and potholes", date="2026-09-01")
    stale = dict(recent, date_observed="2026-09-01")
    same_day = dict(recent, date_observed="2026-01-02")
    assert find_duplicates(same_day, [old], 0)[0].score > find_duplicates(stale, [old], 0)[0].score


def test_results_sorted_best_first_and_capped():
    existing = [rep(i, "Pothole at junction", "Deep pothole at the junction.", category="Roads and potholes")
                for i in range(1, 9)]
    existing.append(rep(9, "Something else", "Unrelated text about a gate.", category="Roads and potholes"))
    new = rep(10, "Pothole at junction", "Deep pothole at the junction.", category="Roads and potholes")
    matches = find_duplicates(new, existing, threshold=0.0)
    assert len(matches) == 5
    assert [m.score for m in matches] == sorted((m.score for m in matches), reverse=True)


def test_tokenizer_unifies_synonyms_and_plurals():
    assert tokenize("Potholes and craters") == tokenize("pothole hole")
    assert "waste" in tokenize("garbage")
    assert tokenize("flooding drains") == ["flood", "drain"]


def test_detector_meets_minimum_quality_on_labelled_pairs():
    """Regression guard on data/duplicate_pairs.csv (recall favoured over precision)."""
    truth, predicted = [], []
    for pair in load_duplicate_pairs():
        a = rep(1, pair["title_a"], pair["desc_a"], community=pair["community_a"], date=pair["date_a"])
        b = rep(2, pair["title_b"], pair["desc_b"], community=pair["community_b"], date=pair["date_b"])
        a["ai_category"] = classify_by_rules(a)["category"]
        b["ai_category"] = classify_by_rules(b)["category"]
        truth.append(pair["same_issue"])
        predicted.append(int(bool(find_duplicates(b, [a]))))
    scores = binary_prf(truth, predicted)
    assert scores["recall"] >= 0.8
    assert scores["precision"] >= 0.6
