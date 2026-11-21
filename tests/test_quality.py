import unittest
from nion.quality import inspect, audit

class QualityTests(unittest.TestCase):
    def test_protected_codes(self):
        self.assertIn("codigos_diferentes",inspect(r"Hello \\C[2]friend", "Hola amigo"))
    def test_empty(self):
        self.assertEqual(inspect("Hello",""),["traduccion_vacia"])
    def test_safe(self):
        self.assertEqual(inspect("Good morning","Buenos dias"),[])
    def test_audit(self):
        self.assertEqual(len(audit({"Hello":"Hola","Long greeting":"Long greeting"})),1)

if __name__=="__main__":
    unittest.main()
