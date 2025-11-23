from testcontainers.postgres import PostgresContainer
import pytest

postgres = PostgresContainer("postgres:18-alpine")


@pytest.fixture(scope="module", autouse=True)
def postgres_db(request):
    postgres.start()
    request.addfinalizer(lambda: postgres.stop)
    return postgres


def test_foo(postgres_db):
    assert "" == postgres_db.get_connection_url()
