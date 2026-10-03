"""Parsing free-text ingredient lines into structured parts."""

from __future__ import annotations

from app.ingredients import format_quantity, parse_ingredient


def test_parse_basic_unit():
    ingredient = parse_ingredient("200 g flour")
    assert ingredient.quantity == 200
    assert ingredient.unit == "g"
    assert ingredient.name == "flour"


def test_parse_fraction():
    ingredient = parse_ingredient("1/2 tsp salt")
    assert ingredient.quantity == 0.5
    assert ingredient.unit == "tsp"
    assert ingredient.name == "salt"


def test_parse_mixed_number():
    ingredient = parse_ingredient("1 1/2 cups flour")
    assert ingredient.quantity == 1.5
    assert ingredient.unit == "cup"
    assert ingredient.name == "flour"


def test_parse_unicode_fraction():
    ingredient = parse_ingredient("½ cup sugar")
    assert ingredient.quantity == 0.5
    assert ingredient.unit == "cup"
    assert ingredient.name == "sugar"


def test_parse_decimal_comma():
    ingredient = parse_ingredient("1,5 kg potatoes")
    assert ingredient.quantity == 1.5
    assert ingredient.unit == "kg"


def test_parse_range():
    ingredient = parse_ingredient("2-3 cloves garlic")
    assert ingredient.quantity is None
    assert ingredient.quantity_text == "2-3"
    assert ingredient.unit == "clove"
    assert ingredient.name == "garlic"


def test_parse_count_without_unit():
    ingredient = parse_ingredient("3 eggs")
    assert ingredient.quantity == 3
    assert ingredient.unit == ""
    assert ingredient.name == "eggs"


def test_parse_unquantified_line():
    ingredient = parse_ingredient("Salt and pepper to taste")
    assert ingredient.quantity is None
    assert ingredient.unit == ""
    assert ingredient.name == "Salt and pepper to taste"


def test_parse_parenthetical_and_preparation_note():
    ingredient = parse_ingredient("1 tin (400 g) chopped tomatoes, drained")
    assert ingredient.quantity == 1
    assert ingredient.unit == "tin"
    assert ingredient.name == "chopped tomatoes"
    assert "400 g" in ingredient.note
    assert "drained" in ingredient.note


def test_parse_finnish_units():
    assert parse_ingredient("2 rkl oliiviöljyä").unit == "tbsp"
    assert parse_ingredient("1 dl vettä").unit == "dl"
    assert parse_ingredient("1 rs (430 g) kanasuikaleita").unit == "pack"


def test_format_quantity():
    assert format_quantity(2) == "2"
    assert format_quantity(1.5) == "1½"
    assert format_quantity(0.5) == "½"
    assert format_quantity(0.25) == "¼"
    assert format_quantity(0.4) == "0.4"
