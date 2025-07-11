#!/usr/bin/env python3
"""
Seed the database with comprehensive menu data from Deliverect format.
This script processes the complex menu structure with categories, products, modifiers, and variants.
"""

import asyncio
import json
import sys
import os
from decimal import Decimal
from typing import Dict, List, Any, Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

# Add the app directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from app.db_async import get_db, init_database
from app.models.menu_async import (
    MenuItem, MenuCategory, MenuModifierGroup, MenuModifier, MenuNameVariant
)
from app.config import settings
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)

# Your provided menu data
MENU_DATA = [
    {
        "availabilities": [
            {
                "dayOfWeek": 1,
                "endTime": "23:59",
                "startTime": "00:00"
            },
            {
                "dayOfWeek": 2,
                "endTime": "23:59",
                "startTime": "00:00"
            },
            {
                "dayOfWeek": 3,
                "endTime": "23:59",
                "startTime": "00:00"
            },
            {
                "dayOfWeek": 4,
                "endTime": "23:59",
                "startTime": "00:00"
            },
            {
                "dayOfWeek": 5,
                "endTime": "23:59",
                "startTime": "00:00"
            },
            {
                "dayOfWeek": 6,
                "endTime": "23:59",
                "startTime": "00:00"
            },
            {
                "dayOfWeek": 7,
                "endTime": "23:59",
                "startTime": "00:00"
            }
        ],
        "bundles": {},
        "categories": [
            {
                "_id": "67209bfb174a0e5384d4db4f",
                "name": "Steak & Burgers",
                "description": "",
                "descriptionTranslations": {},
                "nameTranslations": {},
                "account": "66b352ef0cd579921543b380",
                "posLocationId": "",
                "posCategoryType": "",
                "posCategoryId": "STK",
                "imageUrl": "",
                "subCategories": [],
                "products": [
                    "6721daafc33216a11b4e239d",
                    "6721daafc33216a11b4e23a2",
                    "66b35629a7eb47d479f1d31b",
                    "66b35629a7eb47d479f1d339",
                    "66b35629a7eb47d479f1d34d",
                    "66b35629a7eb47d479f1d34f",
                    "67209bb4174a0e5384d4d9f5",
                    "67209bb4174a0e5384d4d9f7",
                    "67209bb4174a0e5384d4d9f9"
                ],
                "availabilities": [],
                "level": 0,
                "menu": "67209bfb174a0e5384d4db61",
                "sortedChannelProductIds": [],
                "subProducts": [
                    "6721daafc33216a11b4e239d",
                    "6721daafc33216a11b4e23a2",
                    "66b35629a7eb47d479f1d31b",
                    "66b35629a7eb47d479f1d339",
                    "66b35629a7eb47d479f1d34d",
                    "66b35629a7eb47d479f1d34f",
                    "67209bb4174a0e5384d4d9f5",
                    "67209bb4174a0e5384d4d9f7",
                    "67209bb4174a0e5384d4d9f9"
                ],
                "subProductSortOrder": []
            },
            {
                "_id": "67209bfb174a0e5384d4db54",
                "name": "Chicken",
                "description": "",
                "descriptionTranslations": {},
                "nameTranslations": {},
                "account": "66b352ef0cd579921543b380",
                "posLocationId": "",
                "posCategoryType": "",
                "posCategoryId": "CHK",
                "imageUrl": "",
                "subCategories": [],
                "products": [
                    "66b35629a7eb47d479f1d307",
                    "66b35629a7eb47d479f1d335"
                ],
                "availabilities": [],
                "level": 0,
                "menu": "67209bfb174a0e5384d4db61",
                "sortedChannelProductIds": [],
                "subProducts": [
                    "66b35629a7eb47d479f1d307",
                    "66b35629a7eb47d479f1d335"
                ],
                "subProductSortOrder": []
            },
            {
                "_id": "67209bfb174a0e5384d4db53",
                "name": "Pizzas",
                "description": "",
                "descriptionTranslations": {},
                "nameTranslations": {},
                "account": "66b352ef0cd579921543b380",
                "posLocationId": "",
                "posCategoryType": "",
                "posCategoryId": "PZ",
                "imageUrl": "",
                "subCategories": [],
                "products": [
                    "6721daafc33216a11b4e23b2",
                    "66b35629a7eb47d479f1d377"
                ],
                "availabilities": [],
                "level": 0,
                "menu": "67209bfb174a0e5384d4db61",
                "sortedChannelProductIds": [],
                "subProducts": [
                    "6721daafc33216a11b4e23b2",
                    "66b35629a7eb47d479f1d377"
                ],
                "subProductSortOrder": []
            },
            {
                "_id": "67209bfb174a0e5384d4db52",
                "name": "Poke Bowls",
                "description": "",
                "descriptionTranslations": {},
                "nameTranslations": {},
                "account": "66b352ef0cd579921543b380",
                "posLocationId": "",
                "posCategoryType": "",
                "posCategoryId": "POKB",
                "imageUrl": "",
                "subCategories": [],
                "products": [
                    "6721daafc33216a11b4e23ba"
                ],
                "availabilities": [],
                "level": 0,
                "menu": "67209bfb174a0e5384d4db61",
                "sortedChannelProductIds": [],
                "subProducts": [
                    "6721daafc33216a11b4e23ba"
                ],
                "subProductSortOrder": []
            },
            {
                "_id": "67209bfb174a0e5384d4db50",
                "name": "Sides",
                "description": "",
                "descriptionTranslations": {},
                "nameTranslations": {},
                "account": "66b352ef0cd579921543b380",
                "posLocationId": "",
                "posCategoryType": "",
                "posCategoryId": "SD",
                "imageUrl": "",
                "subCategories": [],
                "products": [
                    "66b35629a7eb47d479f1d309",
                    "66b35629a7eb47d479f1d30b",
                    "66b35629a7eb47d479f1d30d",
                    "66b35629a7eb47d479f1d343"
                ],
                "availabilities": [],
                "level": 0,
                "menu": "67209bfb174a0e5384d4db61",
                "sortedChannelProductIds": [],
                "subProducts": [
                    "66b35629a7eb47d479f1d309",
                    "66b35629a7eb47d479f1d30b",
                    "66b35629a7eb47d479f1d30d",
                    "66b35629a7eb47d479f1d343"
                ],
                "subProductSortOrder": []
            },
            {
                "_id": "67209bfb174a0e5384d4db51",
                "name": "Drinks",
                "description": "",
                "descriptionTranslations": {},
                "nameTranslations": {},
                "account": "66b352ef0cd579921543b380",
                "posLocationId": "",
                "posCategoryType": "",
                "posCategoryId": "DRK",
                "imageUrl": "",
                "subCategories": [],
                "products": [
                    "66b35629a7eb47d479f1d31d",
                    "66b35629a7eb47d479f1d351",
                    "66b35629a7eb47d479f1d353"
                ],
                "availabilities": [],
                "level": 0,
                "menu": "67209bfb174a0e5384d4db61",
                "sortedChannelProductIds": [],
                "subProducts": [
                    "66b35629a7eb47d479f1d31d",
                    "66b35629a7eb47d479f1d351",
                    "66b35629a7eb47d479f1d353"
                ],
                "subProductSortOrder": []
            }
        ],
        "channelLinkId": "66b35566dc02e27b286fca60",
        "currency": 1,
        "description": "***NEW***",
        "descriptionTranslations": {},
        "menu": "***NEW***",
        "menuId": "67209bfb174a0e5384d4db61",
        "menuImageURL": "https://resizer.staging.deliverect.com/AKVTOAAMpx3nutPSwvQhopTfBcoDkgXZwNKGN-h1Oms/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy82NmIzNTJlZjBjZDU3OTkyMTU0M2IzODAvSG9tZW1hZGUtRnJlbmNoLUZyaWVzXzgtNjcyMDk4ZmE5NzJlZTE3ZGQzYjhhYTg0LmpwZw==.jpg",
        "menuType": 0,
        "modifierGroups": {
            "67209bb4174a0e5384d4d9fb": {
                "_id": "67209bb4174a0e5384d4d9fb",
                "name": "Ingredients",
                "description": "",
                "descriptionTranslations": {},
                "nameTranslations": {},
                "account": "66b352ef0cd579921543b380",
                "capacityUsages": [],
                "imageUrl": "",
                "location": "66b35312dc02e27b286fca1b",
                "max": 4,
                "min": 0,
                "multiply": 1,
                "plu": "INGRD",
                "posCategoryIds": [],
                "posProductCategoryId": "",
                "posProductId": "",
                "productTags": [],
                "productType": 3,
                "subProducts": [
                    "67209bb4174a0e5384d4d9fd",
                    "67209bb4174a0e5384d4d9ff",
                    "67209bb4174a0e5384d4da01",
                    "67209bb4174a0e5384d4da03"
                ],
                "parentId": "67209bb4174a0e5384d4d9f9",
                "snoozed": False,
                "subProductSortOrder": []
            }
        },
        "modifiers": {
            "67209bb4174a0e5384d4d9fd": {
                "_id": "67209bb4174a0e5384d4d9fd",
                "name": "Tomatos",
                "description": "",
                "descriptionTranslations": {},
                "nameTranslations": {},
                "account": "66b352ef0cd579921543b380",
                "capacityUsages": [],
                "defaultQuantity": 1,
                "deliveryTax": 9000,
                "eatInTax": 9000,
                "imageUrl": "",
                "location": "66b35312dc02e27b286fca1b",
                "max": 0,
                "min": 0,
                "multiply": 1,
                "plu": "TOMAT",
                "posCategoryIds": [],
                "posProductCategoryId": "",
                "posProductId": "POS-ID-00031",
                "price": 0,
                "productTags": [],
                "productType": 2,
                "subProducts": [],
                "takeawayTax": 9000,
                "parentId": "67209bb4174a0e5384d4d9fb",
                "snoozed": False,
                "subProductSortOrder": []
            }
        },
        "menuTranslations": {},
        "nestedModifiers": False,
        "products": {
            "6721daafc33216a11b4e239d": {
                "_id": "6721daafc33216a11b4e239d",
                "name": "Deluxe Burger (Pick and Choose)",
                "description": "Combo and Nested Modifiers structure",
                "price": 1100,
                "plu": "P-BRGR-1",
                "posCategoryIds": ["STK"],
                "posProductId": "POS-ID-0001",
                "imageUrl": "https://resizer.staging.deliverect.com/ImdZCXJxApx-OZopwAi6tIQPCyyu3fon1TTNkan15Gg/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy82MjIyMDc2Y2E4YmE0ODQ0YmY1MTg0MjUvRGVsdXhlIEJ1cmdlci02NzFiNWE3MDk3MmVlMTdkZDNiOGFhNGYuanBn.jpg",
                "snoozed": False
            },
            "66b35629a7eb47d479f1d31b": {
                "_id": "66b35629a7eb47d479f1d31b",
                "name": "Chicken Burger",
                "description": "Crispy coated chicken thigh, iceberg lettuce, pickles, slice of cheese & mayo, all in a toasted brioche bun.",
                "price": 800,
                "plu": "P-BURG-CHK",
                "posCategoryIds": ["STK"],
                "posProductId": "POS-ID-026",
                "imageUrl": "https://resizer.staging.deliverect.com/By5AsW4yrHpO2XEkTpT59gT0ojYuFArr5krZnUIyeAI/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy81ZmY2ZWUwODkzMjhjOGFlZmVlYWJlMzMvY2hrYnVyZ2VyLTYyMjhjMWRjZGI1OTg2MDAxZWJmNThkZi5qcGVn.jpg",
                "snoozed": False
            },
            "66b35629a7eb47d479f1d339": {
                "_id": "66b35629a7eb47d479f1d339",
                "name": "Delicious Steak Frites",
                "description": "Basic Example Product with - Modifier groups - min/max variables - default selection - translations",
                "price": 1500,
                "plu": "STK-01",
                "posCategoryIds": ["STK"],
                "posProductId": "POS-ID-001",
                "imageUrl": "https://resizer.staging.deliverect.com/QWXAKnkpH1Md-kCY-7OeMO4I23T2VL7f05RSP1CNic4/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy81ZmY2ZWUwODkzMjhjOGFlZmVlYWJlMzMvc3RlYWstNjIyODYyNTg4YzUwNmYwMTViZTYwMThlLmpwZWc=.jpg",
                "snoozed": False
            },
            "66b35629a7eb47d479f1d34d": {
                "_id": "66b35629a7eb47d479f1d34d",
                "name": "Cheeseburger",
                "description": "100% beef patty, cheddar, caramelized onions, mayonnaise, pickles in a Pretzel bun",
                "price": 850,
                "plu": "P-BURG-CHE",
                "posCategoryIds": ["STK"],
                "posProductId": "POS-ID-027",
                "imageUrl": "https://resizer.staging.deliverect.com/-T3Q86ak_gYss4pfyjoOu0S2ZSz3ivubi9QsNADrk-Q/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy81ZmY2ZWUwODkzMjhjOGFlZmVlYWJlMzMvY2hlZXNlYnVyZ2VyLTYyMjg2ZTI2ZGI1OTg2MDAxZWJmNThkNy5qcGc=.jpg",
                "snoozed": False
            },
            "66b35629a7eb47d479f1d34f": {
                "_id": "66b35629a7eb47d479f1d34f",
                "name": "Veggie Burger",
                "description": "Black bean burgers with sweet potato, mushrooms, quinoa, and pecans.",
                "price": 750,
                "plu": "P-BURG-VEG",
                "posCategoryIds": ["STK"],
                "posProductId": "POS-ID-028",
                "imageUrl": "https://resizer.staging.deliverect.com/N-0UqHpmHxtWoxLug-amn5fhcOtecxOGuk17nqY9Yu0/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy81ZmY2ZWUwODkzMjhjOGFlZmVlYWJlMzMvdmVnZ2llYnVyZ2VyLTYyMjg2Y2JhYzcxNWI0MDNiMGViNzI5NC5qcGVn.jpg",
                "snoozed": False,
                "productTags": [1000]
            },
            "66b35629a7eb47d479f1d307": {
                "_id": "66b35629a7eb47d479f1d307",
                "name": "Chicken Sate",
                "description": "Product with Nested Modifiers - Multimax variables - Allergens (tags)",
                "price": 450,
                "plu": "P-SATE",
                "posCategoryIds": ["CHK"],
                "posProductId": "POS-ID-009",
                "imageUrl": "https://resizer.staging.deliverect.com/dLn-Axhl9HkbXMP0hC8yL3t8OZtlGEFNKD-OPD7LdoY/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy81ZmY2ZWUwODkzMjhjOGFlZmVlYWJlMzMvc2F0YXktNjIyODRlM2M4YzUwNmYwMTViZTYwMTg0LmpwZWc=.jpg",
                "snoozed": False,
                "productTags": [104, 108]
            },
            "66b35629a7eb47d479f1d335": {
                "_id": "66b35629a7eb47d479f1d335",
                "name": "Chicken Tenders",
                "description": "Variant prices for different sizes will show cheapest on top level product",
                "price": 800,
                "plu": "VAR-PROD-1",
                "posCategoryIds": ["CHK"],
                "posProductId": "POS-ID-057",
                "imageUrl": "https://resizer.staging.deliverect.com/RENCGkbBafii4fWRyCwS0VGV6714pL17SxoULs0KgA0/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy81ZmY2ZWUwODkzMjhjOGFlZmVlYWJlMzMvY2hpY2tlbi02MjI4NWY5MGRiNTk4NjAwMWViZjU4ZDUuanBn.jpg",
                "snoozed": False
            },
            "6721daafc33216a11b4e23b2": {
                "_id": "6721daafc33216a11b4e23b2",
                "name": "Build your own Pizza",
                "description": "Build your own pizza, first topping is free!",
                "price": 800,
                "plu": "PIZZ-00",
                "posCategoryIds": ["PZ"],
                "posProductId": "POS-ID-048",
                "imageUrl": "https://resizer.staging.deliverect.com/GD-rbG2fv0sRMVWVHh4fV5rdYOMTqQ5QyAEyHwedQl0/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy81ZmY2ZWUwODkzMjhjOGFlZmVlYWJlMzMvcGl6emEtNjIyODUyNWViMzAzZmMwM2ExNDhkZTQ2LmpwZWc=.jpg",
                "snoozed": False
            },
            "66b35629a7eb47d479f1d377": {
                "_id": "66b35629a7eb47d479f1d377",
                "name": "The Hawaiian",
                "description": "Italy's favourite Pizza!",
                "price": 800,
                "plu": "PIZZ-01",
                "posCategoryIds": ["PZ"],
                "posProductId": "POS-ID-062",
                "imageUrl": "https://resizer.staging.deliverect.com/a7Wji9CAymU-3IBjiBeSmrcqMTvHzmsnOeq8K3ldCBM/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy81ZmY2ZWUwODkzMjhjOGFlZmVlYWJlMzMvaGF3YWlpYW4tNjIyODU1YzdiMzAzZmMwM2ExNDhkZTQ4LmpwZWc=.jpg",
                "snoozed": False
            },
            "6721daafc33216a11b4e23ba": {
                "_id": "6721daafc33216a11b4e23ba",
                "name": "Build a Poke Bowl",
                "description": "Select a size then choose your ingredients",
                "price": 1000,
                "plu": "P-PB-01",
                "posCategoryIds": ["POKB"],
                "posProductId": "POS-ID-032",
                "imageUrl": "https://resizer.staging.deliverect.com/LCTRGFEQdLnvJ6I989O99RTLSDt361uCNd-IpAxrnj0/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy81ZmY2ZWUwODkzMjhjOGFlZmVlYWJlMzMvcG9rZS02MjI4NTBjOGIzMDNmYzAzYTE0OGRlNDQuanBn.jpg",
                "snoozed": False
            },
            "66b35629a7eb47d479f1d309": {
                "_id": "66b35629a7eb47d479f1d309",
                "name": "White Rice",
                "description": "White coloured rice",
                "price": 450,
                "plu": "RICE-01",
                "posCategoryIds": ["SD"],
                "posProductId": "POS-ID-012",
                "imageUrl": "https://resizer.staging.deliverect.com/9ZV8s6bBr11enQLQyFp5x86PDOFtjXVljJdzs_PPpTo/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy81ZmY2ZWUwODkzMjhjOGFlZmVlYWJlMzMvbmFzaXB1dGktMTYxMDI5MDE0MDQ5NC5qcGc=.jpg",
                "snoozed": False
            },
            "66b35629a7eb47d479f1d30b": {
                "_id": "66b35629a7eb47d479f1d30b",
                "name": "Egg Noodles",
                "description": "Egg noodles and veggies fried and tossed with a delicious sauce",
                "price": 450,
                "plu": "NOOD-01",
                "posCategoryIds": ["SD"],
                "posProductId": "POS-ID-014",
                "imageUrl": "https://resizer.staging.deliverect.com/1DOWQmKyNPh0GDpoE-M-V-N6wAkoSBg-PPHNAN3DEWE/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy81ZmY2ZWUwODkzMjhjOGFlZmVlYWJlMzMvYmFtaWdvcmVuZy0xNjEwMjg5OTIyOTY5LmpwZw==.jpg",
                "snoozed": False
            },
            "66b35629a7eb47d479f1d30d": {
                "_id": "66b35629a7eb47d479f1d30d",
                "name": "Ramen Noodles",
                "description": "Chinese-style wheat noodles",
                "price": 450,
                "plu": "NOOD-02",
                "posCategoryIds": ["SD"],
                "posProductId": "POS-ID-015",
                "imageUrl": "https://resizer.staging.deliverect.com/yS_VH1maHnLv7RLw8bCtxIuHDv1bXUJS6LiuocEpFXI/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy81ZmY2ZWUwODkzMjhjOGFlZmVlYWJlMzMvTWlob2VuLTItMS0xNjEwMjg5ODcwMTU3LmpwZw==.jpg",
                "snoozed": False
            },
            "66b35629a7eb47d479f1d343": {
                "_id": "66b35629a7eb47d479f1d343",
                "name": "Yellow Rice",
                "description": "White rice with Saffron",
                "price": 450,
                "plu": "RICE-02",
                "posCategoryIds": ["SD"],
                "posProductId": "POS-ID-013",
                "imageUrl": "https://resizer.staging.deliverect.com/lxSc2sAbetJKPew9FqZS2osLw4zdzsGFgNV9L7sS2XU/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy81ZmY2ZWUwODkzMjhjOGFlZmVlYWJlMzMvTmFzaS1rdW5pbmctMy0xNjEwMjg5NzI2OTQ2LmpwZw==.jpg",
                "snoozed": False
            },
            "66b35629a7eb47d479f1d351": {
                "_id": "66b35629a7eb47d479f1d351",
                "name": "Coca Cola",
                "description": "Cola flavoured sugar and caffeine",
                "price": 400,
                "plu": "DRNK-01",
                "posCategoryIds": ["DRK"],
                "posProductId": "POS-ID-029",
                "imageUrl": "https://resizer.staging.deliverect.com/kZlALx0v9-hlN7m_sK8OZ6IKS1YfRtSIow_VpDTTjRQ/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy81ZmY2ZWUwODkzMjhjOGFlZmVlYWJlMzMvY29jYWNvbGEtNjIyODU0YTc4YzUwNmYwMTViZTYwMThhLmpwZWc=.jpg",
                "snoozed": False
            },
            "66b35629a7eb47d479f1d353": {
                "_id": "66b35629a7eb47d479f1d353",
                "name": "Diet Coke",
                "description": "Cola flavoured aspartame and caffeine",
                "price": 400,
                "plu": "DRNK-02",
                "posCategoryIds": ["DRK"],
                "posProductId": "POS-ID-030",
                "imageUrl": "https://resizer.staging.deliverect.com/Ff1p7WZlT-NAafcnQ6HygbKb5XFbm-p5Uqyfb_lo4P8/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy81ZmY2ZWUwODkzMjhjOGFlZmVlYWJlMzMvZGlldGNva2UtNjIyODU0Y2U4YzUwNmYwMTViZTYwMThjLmpwZWc=.jpg",
                "snoozed": False
            },
            "66b35629a7eb47d479f1d31d": {
                "_id": "66b35629a7eb47d479f1d31d",
                "name": "Ginger Beer",
                "description": "Australia's favourite ginger beer!",
                "price": 500,
                "plu": "DRNK-03",
                "posCategoryIds": ["DRK"],
                "posProductId": "POS-ID-031",
                "imageUrl": "https://resizer.staging.deliverect.com/iFUJT73YtMe1pChj29lAFUt_NBknsyTu5Hlr6NvA5NI/rt:fill/g:ce/el:0/aHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2lrb25hLWJ1Y2tldC1zdGFnaW5nL2ltYWdlcy81ZmY2ZWUwODkzMjhjOGFlZmVlYWJlMzMvZ2luZ2VyYmVlci02MjI4NTU0OGRiNTk4NjAwMWViZjU4ZDEuanBn.jpg",
                "snoozed": False
            }
        },
        "productTags": [
            1000,
            104,
            108
        ],
        "snoozedProducts": {},
        "validations": []
    }
]


async def clear_existing_data(db):
    """Clear existing menu data to start fresh."""
    logger.info("Clearing existing menu data...")
    
    # Clear in reverse dependency order (only tables that exist)
    await db.execute(text("DELETE FROM menu_name_variants"))
    await db.execute(text("DELETE FROM group_modifier"))
    await db.execute(text("DELETE FROM item_modifier_group"))
    await db.execute(text("DELETE FROM menu_modifiers"))
    await db.execute(text("DELETE FROM modifier_groups"))
    await db.execute(text("DELETE FROM menu_items"))
    await db.execute(text("DELETE FROM menu_categories"))
    
    await db.commit()
    logger.info("✅ Existing menu data cleared")


async def create_categories(db, categories_data: List[Dict[str, Any]]) -> Dict[str, int]:
    """Create menu categories and return mapping of external_id -> internal_id."""
    logger.info("Creating menu categories...")
    category_mapping = {}
    
    for cat_data in categories_data:
        category = MenuCategory(
            deliverect_category_id=cat_data["_id"],
            name=cat_data["name"],
            description=cat_data.get("description", ""),
            order_index=cat_data.get("level", 0)
        )
        
        db.add(category)
        await db.flush()  # Get the ID
        category_mapping[cat_data["_id"]] = category.id
        
        logger.info(f"Created category: {category.name} (ID: {category.id})")
    
    await db.commit()
    return category_mapping


async def create_modifier_groups(db, modifier_groups_data: Dict[str, Any]) -> Dict[str, int]:
    """Create modifier groups and return mapping."""
    logger.info("Creating modifier groups...")
    group_mapping = {}
    
    for group_id, group_data in modifier_groups_data.items():
        modifier_group = MenuModifierGroup(
            deliverect_group_id=group_data["_id"],
            name=group_data["name"],
            min_selection=group_data.get("min", 0),
            max_selection=group_data.get("max", 0),
            multiMax=group_data.get("multiMax", 0),
            plu=group_data.get("plu", ""),
            is_variant_group=group_data.get("isVariantGroup", False)
        )
        
        db.add(modifier_group)
        await db.flush()
        group_mapping[group_data["_id"]] = modifier_group.id
        
        logger.info(f"Created modifier group: {modifier_group.name} (ID: {modifier_group.id})")
    
    await db.commit()
    return group_mapping


async def create_modifiers(db, modifiers_data: Dict[str, Any], group_mapping: Dict[str, int]) -> Dict[str, int]:
    """Create modifiers and return mapping."""
    logger.info("Creating modifiers...")
    modifier_mapping = {}
    
    for modifier_id, modifier_data in modifiers_data.items():
        # Convert price from cents to dollars
        price_cents = modifier_data.get("price", 0)
        price_change = Decimal(str(price_cents)) / 100 if price_cents else Decimal('0.00')
        
        modifier = MenuModifier(
            deliverect_modifier_id=modifier_data["_id"],
            name=modifier_data["name"],
            price_change=price_change,
            plu=modifier_data.get("plu", ""),
            is_available=not modifier_data.get("snoozed", False)
        )
        
        db.add(modifier)
        await db.flush()
        modifier_mapping[modifier_data["_id"]] = modifier.id
        
        logger.info(f"Created modifier: {modifier.name} (ID: {modifier.id}, Price change: ${price_change})")
    
    await db.commit()
    return modifier_mapping


async def create_products(db, products_data: Dict[str, Any], category_mapping: Dict[str, int]) -> Dict[str, int]:
    """Create menu items (products) and return mapping."""
    logger.info("Creating menu items...")
    item_mapping = {}
    
    for product_id, product_data in products_data.items():
        # Find category this product belongs to
        category_id = None
        pos_category_ids = product_data.get("posCategoryIds", [])
        if pos_category_ids:
            # Find category by pos_category_id
            for cat_external_id, cat_internal_id in category_mapping.items():
                # We need to look up the category to get its pos_category_id
                # For now, we'll map based on the data structure
                pass
        
        # Convert price from cents to dollars
        price_cents = product_data.get("price", 0)
        price = Decimal(str(price_cents)) / 100 if price_cents else Decimal('0.00')
        
        menu_item = MenuItem(
            deliverect_item_id=product_data["_id"],
            name=product_data["name"],
            description=product_data.get("description", ""),
            price=price,
            category_id=category_id,  # We'll update this after processing categories
            is_available=not product_data.get("snoozed", False),
            image_url=product_data.get("imageUrl", ""),
            order_index=0,
            plu=product_data.get("plu", ""),
            is_combo=product_data.get("isCombo", False),
            is_variant=product_data.get("isVariant", False)
        )
        
        db.add(menu_item)
        await db.flush()
        item_mapping[product_data["_id"]] = menu_item.id
        
        # Store PLU in menu item for now (until PLU model is created)
        plu_code = product_data.get("plu")
        if plu_code:
            # For now, we'll store it as additional data
            pass
            
        # Create name variants for voice recognition
        await create_name_variants(db, menu_item, product_data)
        
        logger.info(f"Created menu item: {menu_item.name} (ID: {menu_item.id}, PLU: {plu_code}, Price: ${price})")
    
    await db.commit()
    return item_mapping


async def create_name_variants(db, menu_item: MenuItem, product_data: Dict[str, Any]):
    """Create name variants for voice recognition."""
    # Primary name
    primary_variant = MenuNameVariant(
        variant_phrase=menu_item.name.lower(),
        canonical_name=menu_item.name,
        target_plu=menu_item.plu or "",
        score=1.0
    )
    db.add(primary_variant)
    
    # Add common variations
    name = menu_item.name.lower()
    
    # Remove common words and create variants
    variants = []
    
    # Create shortened versions
    words = name.split()
    if len(words) > 1:
        # First word only
        variants.append(words[0])
        # Last word only  
        variants.append(words[-1])
        # First and last word
        if len(words) > 2:
            variants.append(f"{words[0]} {words[-1]}")
    
    # Add specific variants based on item type
    if "burger" in name:
        variants.extend(["burger", "burg"])
    if "chicken" in name:
        variants.extend(["chook", "chick"])
    if "fries" in name:
        variants.extend(["chips", "fry"])
    if "coca cola" in name or "coke" in name:
        variants.extend(["coke", "cola", "coca cola"])
    if "diet" in name:
        variants.extend(["diet coke", "diet"])
    if "pizza" in name:
        variants.extend(["pizza", "piza"])
    if "poke" in name:
        variants.extend(["poki", "pokey"])
    
    # Special case: map common burger variants to the closest actual item
    if name.lower() == "cheeseburger":
        variants.extend(["classic burger", "regular burger", "plain burger", "basic burger", "beef burger"])
    
    # Create variant records
    for i, variant in enumerate(set(variants)):  # Remove duplicates
        if variant and variant != name:
            variant_record = MenuNameVariant(
                variant_phrase=variant,
                canonical_name=name,
                target_plu=menu_item.plu or "",
                score=0.8 - (i * 0.1)  # Decreasing confidence
            )
            db.add(variant_record)


async def update_category_assignments(db, products_data: Dict[str, Any], categories_data: List[Dict[str, Any]], 
                                    category_mapping: Dict[str, int], item_mapping: Dict[str, int]):
    """Update category assignments for menu items."""
    logger.info("Updating category assignments...")
    
    # Create mapping of category external_id to pos_category_id
    pos_category_mapping = {}
    for cat_data in categories_data:
        pos_category_mapping[cat_data.get("posCategoryId", "")] = category_mapping[cat_data["_id"]]
    
    # Update each product
    for product_id, product_data in products_data.items():
        item_id = item_mapping.get(product_id)
        if not item_id:
            continue
            
        pos_category_ids = product_data.get("posCategoryIds", [])
        if pos_category_ids:
            # Use the first pos_category_id
            pos_cat_id = pos_category_ids[0]
            category_id = pos_category_mapping.get(pos_cat_id)
            
            if category_id:
                # Update the menu item
                result = await db.execute(
                    text("UPDATE menu_items SET category_id = :cat_id WHERE id = :item_id"),
                    {"cat_id": category_id, "item_id": item_id}
                )
                logger.info(f"Updated item {product_data['name']} -> category {pos_cat_id}")
    
    await db.commit()


async def seed_menu_database():
    """Main function to seed the menu database."""
    logger.info("🌱 Starting menu database seeding...")
    
    try:
        # Initialize database
        await init_database()
        
        async for db in get_db():
            # Clear existing data
            await clear_existing_data(db)
            
            # Process menu data
            menu_data = MENU_DATA[0]  # Get the first (and only) menu
            
            # Create categories
            category_mapping = await create_categories(db, menu_data["categories"])
            
            # Create modifier groups  
            group_mapping = await create_modifier_groups(db, menu_data.get("modifierGroups", {}))
            
            # Create modifiers
            modifier_mapping = await create_modifiers(db, menu_data.get("modifiers", {}), group_mapping)
            
            # Create products (menu items)
            item_mapping = await create_products(db, menu_data.get("products", {}), category_mapping)
            
            # Update category assignments
            await update_category_assignments(
                db, menu_data.get("products", {}), menu_data["categories"], 
                category_mapping, item_mapping
            )
            
            # Print summary
            logger.info("🎉 Menu seeding completed successfully!")
            logger.info(f"📊 Summary:")
            logger.info(f"   - Categories: {len(category_mapping)}")
            logger.info(f"   - Modifier Groups: {len(group_mapping)}")
            logger.info(f"   - Modifiers: {len(modifier_mapping)}")
            logger.info(f"   - Menu Items: {len(item_mapping)}")
            
            break  # Exit the async generator
            
    except Exception as e:
        logger.error(f"❌ Error seeding menu database: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(seed_menu_database())