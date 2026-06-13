"""
Nexus v2
Checkpoint Manager
"""

from pathlib import Path
import pandas as pd


class CheckpointManager:

    def __init__(
        self,
        checkpoint_file
    ):

        self.checkpoint_file = (
            Path(checkpoint_file)
        )

    # ============================
    # LOAD
    # ============================

    def load(self):

        if not (
            self.checkpoint_file.exists()
        ):

            return pd.DataFrame()

        return pd.read_csv(
            self.checkpoint_file
        )

    # ============================
    # SAVE RECORD
    # ============================

    def save_record(
        self,
        record
    ):

        df = pd.DataFrame(
            [record]
        )

        file_exists = (
            self.checkpoint_file.exists()
        )

        df.to_csv(

            self.checkpoint_file,

            mode=
            "a" if file_exists else "w",

            header=
            not file_exists,

            index=False
        )

    # ============================
    # HASHES
    # ============================

    def processed_hashes(self):

        df = self.load()

        if df.empty:

            return set()

        if (
            "file_hash"
            not in df.columns
        ):

            return set()

        return set(

            df[
                "file_hash"
            ]

            .dropna()

            .tolist()
        )

    # ============================
    # EXISTS
    # ============================

    def already_processed(
        self,
        file_hash
    ):

        return (
            file_hash
            in
            self.processed_hashes()
        )

    # ============================
    # CLEAR
    # ============================

    def clear(self):

        if (
            self.checkpoint_file.exists()
        ):

            self.checkpoint_file.unlink()

    # ============================
    # STATS
    # ============================

    def stats(self):

        df = self.load()

        if df.empty:

            return {

                "records": 0
            }

        return {

            "records":
            len(df)
        }