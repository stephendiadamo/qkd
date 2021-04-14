import unittest


class TestProtocols(unittest.TestCase):

    # Runs before all tests
    @classmethod
    def setUpClass(cls) -> None:
        pass

    # Runs after all tests
    @classmethod
    def tearDownClass(cls) -> None:
        pass

    # Runs before each test
    def setUp(self) -> None:
        pass

    # Runs after each test
    def tearDown(self) -> None:
        pass

    def test_instantiation(self):
        pass

    def test_bb84_noiseless(self):
        pass

    def test_e91_noiseless(self):
        pass

    def test_b92_noiseless(self):
        pass

    def test_bbm92_noiseless(self):
        pass
