"""Use physical paths for temporary roots owned by the test harness."""

import pytest


@pytest.fixture
def tmp_path(tmp_path):
    # macOS temp roots can arrive through /var -> /private/var. Resolve before
    # tests create any links; never resolve user-controlled research paths.
    return tmp_path.resolve(strict=True)
