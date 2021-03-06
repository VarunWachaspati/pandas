from io import BytesIO
import os

import numpy as np
import pytest

from pandas import DataFrame, date_range, read_csv
import pandas._testing as tm
from pandas.util import _test_decorators as td


@pytest.fixture
def gcs_buffer(monkeypatch):
    """Emulate GCS using a binary buffer."""
    from fsspec import AbstractFileSystem, registry

    registry.target.clear()  # noqa  # remove state

    gcs_buffer = BytesIO()
    gcs_buffer.close = lambda: True

    class MockGCSFileSystem(AbstractFileSystem):
        def open(*args, **kwargs):
            gcs_buffer.seek(0)
            return gcs_buffer

    monkeypatch.setattr("gcsfs.GCSFileSystem", MockGCSFileSystem)

    return gcs_buffer


@td.skip_if_no("gcsfs")
def test_read_csv_gcs(gcs_buffer):
    from fsspec import registry

    registry.target.clear()  # noqa  # remove state

    df1 = DataFrame(
        {
            "int": [1, 3],
            "float": [2.0, np.nan],
            "str": ["t", "s"],
            "dt": date_range("2018-06-18", periods=2),
        }
    )

    gcs_buffer.write(df1.to_csv(index=False).encode())

    df2 = read_csv("gs://test/test.csv", parse_dates=["dt"])

    tm.assert_frame_equal(df1, df2)


@td.skip_if_no("gcsfs")
def test_to_csv_gcs(gcs_buffer):
    from fsspec import registry

    registry.target.clear()  # noqa  # remove state

    df1 = DataFrame(
        {
            "int": [1, 3],
            "float": [2.0, np.nan],
            "str": ["t", "s"],
            "dt": date_range("2018-06-18", periods=2),
        }
    )

    df1.to_csv("gs://test/test.csv", index=True)

    df2 = read_csv("gs://test/test.csv", parse_dates=["dt"], index_col=0)

    tm.assert_frame_equal(df1, df2)


@td.skip_if_no("gcsfs")
@pytest.mark.parametrize("encoding", ["utf-8", "cp1251"])
def test_to_csv_compression_encoding_gcs(gcs_buffer, compression_only, encoding):
    """
    Compression and encoding should with GCS.

    GH 35677 (to_csv, compression), GH 26124 (to_csv, encoding), and
    GH 32392 (read_csv, encoding)
    """
    from fsspec import registry

    registry.target.clear()  # noqa  # remove state
    df = tm.makeDataFrame()

    # reference of compressed and encoded file
    compression = {"method": compression_only}
    if compression_only == "gzip":
        compression["mtime"] = 1  # be reproducible
    buffer = BytesIO()
    df.to_csv(buffer, compression=compression, encoding=encoding, mode="wb")

    # write compressed file with explicit compression
    path_gcs = "gs://test/test.csv"
    df.to_csv(path_gcs, compression=compression, encoding=encoding)
    assert gcs_buffer.getvalue() == buffer.getvalue()
    read_df = read_csv(
        path_gcs, index_col=0, compression=compression_only, encoding=encoding
    )
    tm.assert_frame_equal(df, read_df)

    # write compressed file with implicit compression
    if compression_only == "gzip":
        compression_only = "gz"
    compression["method"] = "infer"
    path_gcs += f".{compression_only}"
    df.to_csv(path_gcs, compression=compression, encoding=encoding)
    assert gcs_buffer.getvalue() == buffer.getvalue()
    read_df = read_csv(path_gcs, index_col=0, compression="infer", encoding=encoding)
    tm.assert_frame_equal(df, read_df)


@td.skip_if_no("fastparquet")
@td.skip_if_no("gcsfs")
def test_to_parquet_gcs_new_file(monkeypatch, tmpdir):
    """Regression test for writing to a not-yet-existent GCS Parquet file."""
    from fsspec import AbstractFileSystem, registry

    registry.target.clear()  # noqa  # remove state
    df1 = DataFrame(
        {
            "int": [1, 3],
            "float": [2.0, np.nan],
            "str": ["t", "s"],
            "dt": date_range("2018-06-18", periods=2),
        }
    )

    class MockGCSFileSystem(AbstractFileSystem):
        def open(self, path, mode="r", *args):
            if "w" not in mode:
                raise FileNotFoundError
            return open(os.path.join(tmpdir, "test.parquet"), mode)

    monkeypatch.setattr("gcsfs.GCSFileSystem", MockGCSFileSystem)
    df1.to_parquet(
        "gs://test/test.csv", index=True, engine="fastparquet", compression=None
    )


@td.skip_if_installed("gcsfs")
def test_gcs_not_present_exception():
    with pytest.raises(ImportError) as e:
        read_csv("gs://test/test.csv")
        assert "gcsfs library is required" in str(e.value)
