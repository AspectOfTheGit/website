import importlib
import json
import os
import sys
import types
import unittest


class FakeS3Client:
    def __init__(self):
        self.objects = {}

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise KeyError(Key)
        return {"Body": self.objects[Key]}

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.objects[Key] = type("Body", (), {"read": lambda self: Body})()


class DataStorageTests(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("R2_ACCOUNT_ID", "test-account")
        os.environ.setdefault("R2_ACCESS_KEY_ID", "test-key")
        os.environ.setdefault("R2_SECRET_ACCESS_KEY", "test-secret")

        fake_boto3 = types.ModuleType("boto3")
        fake_boto3.client = lambda *args, **kwargs: FakeS3Client()
        sys.modules["boto3"] = fake_boto3

        sys.modules.pop("src.data", None)
        self.data_module = importlib.import_module("src.data")
        self.data_module.s3 = FakeS3Client()
        self.data_module.data = self.data_module.DataStore()

    def test_saves_account_data_into_account_folder_and_loads_it_back(self):
        self.data_module.data.update({
            "bot": {},
            "account": {
                "acc-123": {
                    "username": "TestUser",
                    "abilities": {"capacity": 2},
                }
            },
            "world": {},
        })

        self.data_module.save_data()

        self.assertIn("data/accounts/acc-123/data.json", self.data_module.s3.objects)
        self.assertIn("data/manifest.json", self.data_module.s3.objects)

        self.data_module.data = self.data_module.DataStore()
        self.data_module.load_data()

        self.assertEqual(self.data_module.data["account"]["acc-123"]["username"], "TestUser")
        self.assertEqual(self.data_module.data["account"]["acc-123"]["abilities"]["capacity"], 2)

    def test_load_data_migrates_legacy_single_file_storage(self):
        payload = json.dumps({
            "account": {
                "acc-123": {
                    "username": "LegacyUser",
                    "abilities": {"capacity": 3},
                }
            },
            "world": {},
            "bot": {},
        }).encode("utf-8")
        self.data_module.s3.objects["data.json"] = type(
            "Body",
            (),
            {"read": lambda self: payload},
        )()

        self.data_module.load_data()

        self.assertEqual(self.data_module.data["account"]["acc-123"]["username"], "LegacyUser")
        self.assertIn("data/accounts/acc-123/data.json", self.data_module.s3.objects)
        self.assertIn("data/manifest.json", self.data_module.s3.objects)


if __name__ == "__main__":
    unittest.main()
