import pytest

from scripts.deploy.setup_cloud import PROJECT_REF, check_database_url

GOOD = f"postgresql://postgres.{PROJECT_REF}:pw@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"


def test_the_pooler_string_of_this_project_is_accepted():
    assert check_database_url(GOOD) is None


@pytest.mark.parametrize("url", [
    "", "https://x", GOOD.replace(":pw@", ":[YOUR-PASSWORD]@"), GOOD.replace(":pw@", "@"),
    GOOD.replace(PROJECT_REF, "proygdwdngbbicfokdrv"),
    f"postgresql://postgres:pw@db.{PROJECT_REF}.supabase.co:5432/postgres"])
def test_other_strings_are_refused(url):
    assert check_database_url(url)
