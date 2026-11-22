import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from siparis.builder import IndividualOrderBuilder
from siparis.menu import default_catalog
from siparis.order import Customer


@pytest.fixture
def menu():
    return default_catalog()


@pytest.fixture
def customer():
    return Customer("C-T", "Test Kullanıcı", "0500 000 00 00")


@pytest.fixture
def simple_order(menu, customer):
    return (IndividualOrderBuilder()
            .for_customer(customer)
            .add_item(menu["burger"])
            .add_item(menu["ayran"])
            .deliver_to("Test Sok. 1", 3.0)
            .build())
