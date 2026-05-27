import unittest

import ecom_runtime


class EcomRuntimeTreeTests(unittest.TestCase):
    def test_tree_with_line_counts_matches_old_runtime_shape(self) -> None:
        original_tree_data = ecom_runtime.tree_data
        original_read = ecom_runtime.read

        def fake_tree_data(path="/", level=0):
            return ecom_runtime.TreeResult(
                root=ecom_runtime.TreeNode(
                    name="",
                    kind="dir",
                    children=[
                        ecom_runtime.TreeNode(name="docs", kind="dir", children=[
                            ecom_runtime.TreeNode(name="policy.md", kind="file"),
                        ]),
                        ecom_runtime.TreeNode(name="item.json", kind="file"),
                    ],
                ),
                truncated=False,
            )

        def fake_read(path, number=False, start_line=0, end_line=0):
            content = "a\nb\n" if path.endswith("policy.md") else "x\ny"
            return ecom_runtime.ReadResult(path=path, content_type="text/plain", content=content)

        ecom_runtime.tree_data = fake_tree_data
        ecom_runtime.read = fake_read
        try:
            text = ecom_runtime.tree_with_line_counts("/")
        finally:
            ecom_runtime.tree_data = original_tree_data
            ecom_runtime.read = original_read

        self.assertEqual(text, "/\n  docs/\n    policy.md [2]\n  item.json [2]")


if __name__ == "__main__":
    unittest.main()
