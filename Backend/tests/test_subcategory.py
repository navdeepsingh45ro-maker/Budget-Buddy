from services.subcategory_rules import detect_subcategory


def test_known_merchants_and_from_at_names():
    assert detect_subcategory("pizza from Pizza Hut") == "Pizza Hut"
    assert detect_subcategory("Swiggy dinner") == "Swiggy"
    assert detect_subcategory("Amazon Prime renewal") == "Amazon Prime"   # longest phrase wins
    assert detect_subcategory("lunch at Barbeque Nation") == "Barbeque Nation"
    assert detect_subcategory("gave money to dad") == "Dad"


def test_no_false_matches():
    assert detect_subcategory("olive oil") is None          # not "Ola"
    assert detect_subcategory("groceries") is None
    assert detect_subcategory("") is None and detect_subcategory(None) is None
