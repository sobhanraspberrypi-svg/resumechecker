"""
Nexus v2
Status Tracker
"""

from datetime import datetime
import pandas as pd


class StatusTracker:

    def __init__(self):

        self.records = {}

    def update(

        self,

        file_hash,

        status,

        notes=""

    ):

        self.records[file_hash] = {

            "status":
            status,

            "notes":
            notes,

            "updated_at":
            datetime.utcnow().isoformat()
        }

    def get_status(
        self,
        file_hash
    ):

        return self.records.get(
            file_hash,
            {}
        )

    def exists(
        self,
        file_hash
    ):

        return file_hash in self.records

    def total_processed(self):

        return len(
            self.records
        )

    def success_count(self):

        return sum(

            1

            for item
            in self.records.values()

            if item["status"]
            == "Success"
        )

    def failed_count(self):

        return sum(

            1

            for item
            in self.records.values()

            if item["status"]
            == "Failed"
        )

    def duplicate_count(self):

        return sum(

            1

            for item
            in self.records.values()

            if item["status"]
            == "Duplicate"
        )

    def to_dataframe(self):

        rows = []

        for file_hash, value in (

            self.records.items()
        ):

            rows.append({

                "File Hash":
                file_hash,

                "Status":
                value["status"],

                "Notes":
                value["notes"],

                "Updated At":
                value["updated_at"]
            })

        return pd.DataFrame(
            rows
        )

    def reset(self):

        self.records = {}