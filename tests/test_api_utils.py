import pytest
import os

os.sys.path.append("..")  # TODO change this when the project structure is changed
from api_utils import ApiAuth


@pytest.fixture
def roster_file():
    return "tests/roster.dummy.tsv"


def test_ApiAuth(roster_file):
    auth = ApiAuth(roster_file)

    assert len(auth.mapping) == 1
    assert len(auth.reverse_mapping) == 1

    assert auth.is_valid_user("12") == False
    assert auth.is_valid_user("111111") == True
    assert (
        auth.is_valid_key(
            "2bdfbb6f76b67ed8cbbbb1ae24e056e757a7d0e665a042c33dd7543bd4160abf"
        )
        == True
    )

    assert (
        auth.get_user(
            "2bdfbb6f76b67ed8cbbbb1ae24e056e757a7d0e665a042c33dd7543bd4160abf"
        )
        == "111111"
    )
    assert (
        auth.get_api_key("111111")
        == "2bdfbb6f76b67ed8cbbbb1ae24e056e757a7d0e665a042c33dd7543bd4160abf"
    )

    assert auth.get_api_key("11") == None
    assert auth.get_user("sakjldqww") == None