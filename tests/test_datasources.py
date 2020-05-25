# Stdlib imports
import sys
from io import BytesIO
from unittest import mock

# Third-party imports
import numpy as np
import pandas as pd
import pytest

# Project imports
import mllaunchpad.datasources as mllp_ds


@pytest.fixture()
def filedatasource_cfg_and_file():
    def _inner(file_type):
        cfg = {
            "type": file_type,
            "path": "blabla",
            "expires": 0,
            "tags": ["train"],
            "options": {},
        }
        if file_type == "euro_csv":
            return (
                cfg,
                b"""
"a";"b";"c"
1,1;"ad";f,afd
2,3;"df";2.3
""",
            )
        elif file_type == "csv":
            return (
                cfg,
                b"""
"a","b","c"
1.1,"ad",f;afd
2.3,"df","2,3"
""",
            )
        else:
            return cfg, b"Hello world!"

    return _inner


@pytest.mark.parametrize("file_type", ["csv", "euro_csv"])
def test_filedatasource_df(file_type, filedatasource_cfg_and_file):
    cfg, file = filedatasource_cfg_and_file(file_type)
    cfg["path"] = BytesIO(file)  # sort-of mocking the file for pandas to open
    ds = mllp_ds.FileDataSource("bla", cfg)
    df = ds.get_dataframe()
    assert str(df["a"].dtype) == "float64"
    assert df["a"][1] == 2.3
    assert df["b"][0] == "ad"


def test_filedatasource_df_chunksize(filedatasource_cfg_and_file):
    cfg, file = filedatasource_cfg_and_file("csv")
    cfg["path"] = BytesIO(file)  # sort-of mocking the file for pandas to open
    ds = mllp_ds.FileDataSource("bla", cfg)
    df_iter = ds.get_dataframe(chunksize=1)
    df1, df2 = df_iter
    assert not isinstance(df_iter, pd.DataFrame)
    assert isinstance(df1, pd.DataFrame)
    assert isinstance(df2, pd.DataFrame)


@pytest.mark.parametrize("file_type", ["text_file", "binary_file"])
def test_filedatasource_raw(file_type, filedatasource_cfg_and_file):
    cfg, file = filedatasource_cfg_and_file(file_type)
    mo = mock.mock_open(read_data=file)
    mo.return_value.name = "./foobar"
    with mock.patch("builtins.open", mo, create=True):
        ds = mllp_ds.FileDataSource("bla", cfg)
        raw = ds.get_raw()
        if isinstance(raw, bytes):
            assert raw == b"Hello world!"
        elif isinstance(raw, str):
            assert raw == "Hello world!"
        else:
            assert False  # Unsupported type


def test_filedatasource_notimplemented(filedatasource_cfg_and_file):
    cfg, _ = filedatasource_cfg_and_file("csv")
    ds = mllp_ds.FileDataSource("bla", cfg)
    with pytest.raises(NotImplementedError):
        ds.get_dataframe(params={"a": "hallo"})
    with pytest.raises(TypeError, match="get_dataframe"):
        ds.get_raw()

    cfg, _ = filedatasource_cfg_and_file("text_file")
    ds = mllp_ds.FileDataSource("bla", cfg)
    with pytest.raises(NotImplementedError):
        ds.get_raw(params={"a": "hallo"})
    with pytest.raises(TypeError, match="get_raw"):
        ds.get_dataframe()

    cfg["type"] = "sausage"
    with pytest.raises(TypeError, match="file type"):
        mllp_ds.FileDataSource("bla", cfg)


@pytest.fixture()
def filedatasink_cfg_and_data():
    def _inner(file_type, options=None):
        options = {} if options is None else options
        cfg = {
            "type": file_type,
            "path": "blabla",
            "tags": ["train"],
            "options": options,
        }
        if file_type == "text_file":
            return cfg, "Hello world!"
        elif file_type == "binary_file":
            return cfg, b"Hello world!"
        else:
            return cfg, pd.DataFrame({"a": [1, 2, 3], "b": [3, 4, 5]})

    return _inner


@pytest.mark.parametrize(
    "file_type, to_csv_params",
    [
        ("csv", {"index": False}),
        ("euro_csv", {"sep": ";", "decimal": ",", "index": False}),
    ],
)
@mock.patch("pandas.DataFrame.to_csv")
def test_filedatasink_df(
    read_sql_mock, file_type, to_csv_params, filedatasink_cfg_and_data
):
    cfg, data = filedatasink_cfg_and_data(file_type)
    ds = mllp_ds.FileDataSink("bla", cfg)
    ds.put_dataframe(data)
    read_sql_mock.assert_called_once_with(cfg["path"], **to_csv_params)


@mock.patch("pandas.DataFrame.to_csv")
def test_filedatasink_df_options(read_sql_mock, filedatasink_cfg_and_data):
    options = {"index": True, "sep": "?"}
    cfg, data = filedatasink_cfg_and_data("csv", options=options)
    ds = mllp_ds.FileDataSink("bla", cfg)
    ds.put_dataframe(data)
    read_sql_mock.assert_called_once_with(cfg["path"], **options)


@pytest.mark.parametrize(
    "file_type, mode", [("text_file", "w"), ("binary_file", "wb")]
)
def test_filedatasink_raw(file_type, mode, filedatasink_cfg_and_data):
    cfg, data = filedatasink_cfg_and_data(file_type)
    mo = mock.mock_open()
    mo.return_value.name = "./foobar"
    with mock.patch("builtins.open", mo, create=True):
        ds = mllp_ds.FileDataSink("bla", cfg)
        ds.put_raw(data)
        mo.assert_called_once_with(cfg["path"], mode)


def test_filedatasink_notimplemented(filedatasink_cfg_and_data):
    cfg, data = filedatasink_cfg_and_data("csv")
    ds = mllp_ds.FileDataSink("bla", cfg)
    with pytest.raises(NotImplementedError):
        ds.put_dataframe(data, params={"a": "hallo"})
    with pytest.raises(TypeError, match="put_dataframe"):
        ds.put_raw(data)

    cfg, data = filedatasink_cfg_and_data("text_file")
    ds = mllp_ds.FileDataSink("bla", cfg)
    with pytest.raises(NotImplementedError):
        ds.put_raw(data, params={"a": "hallo"})
    with pytest.raises(TypeError, match="put_raw"):
        ds.put_dataframe(data)

    cfg["type"] = "sausage"
    with pytest.raises(TypeError, match="file type"):
        mllp_ds.FileDataSink("bla", cfg)


@pytest.fixture()
def oracledatasource_cfg_and_data():
    def _inner(options=None):
        options = {} if options is None else options
        cfg = {
            "type": "dbms.my_connection",
            "query": "blabla",
            "tags": ["train"],
            "options": options,
        }
        dbms_cfg = {
            "type": "oracle",
            "host": "host.example.com",
            "port": 1251,
            "user_var": "MY_USER_ENV_VAR",
            "password_var": "MY_PW_ENV_VAR",
            "service_name": "servicename.example.com",
            "options": options,
        }
        return cfg, dbms_cfg, pd.DataFrame({"a": [1, 2, 3], "b": [3, 4, 5]})

    return _inner


@mock.patch("pandas.read_sql")
@mock.patch(
    "{}.get_user_pw".format(mllp_ds.__name__), return_value=("foo", "bar")
)
def test_oracledatasource_df(user_pw, pd_read, oracledatasource_cfg_and_data):
    """OracleDataSource should connect, read dataframe and return it unaltered."""
    cfg, dbms_cfg, data = oracledatasource_cfg_and_data()
    ora_mock = mock.MagicMock()
    sys.modules["cx_Oracle"] = ora_mock
    pd_read.return_value = data

    ds = mllp_ds.OracleDataSource("bla", cfg, dbms_cfg)
    df = ds.get_dataframe()

    pd.testing.assert_frame_equal(df, data)
    ora_mock.connect.assert_called_once()
    pd_read.assert_called_once()

    del sys.modules["cx_Oracle"]


@mock.patch("pandas.read_sql")
@mock.patch(
    "{}.get_user_pw".format(mllp_ds.__name__), return_value=("foo", "bar")
)
def test_oracledatasource_df_chunksize(
    user_pw, pd_read, oracledatasource_cfg_and_data
):
    """OracleDataSource with chunksize should return generator."""
    cfg, dbms_cfg, full_data = oracledatasource_cfg_and_data()
    iter_data = [full_data.iloc[:2, :].copy(), full_data.iloc[2:, :].copy()]
    ora_mock = mock.MagicMock()
    sys.modules["cx_Oracle"] = ora_mock
    pd_read.return_value = iter_data

    ds = mllp_ds.OracleDataSource("bla", cfg, dbms_cfg)
    df_gen = ds.get_dataframe(chunksize=2)

    for df, orig in zip(df_gen, iter_data):
        pd.testing.assert_frame_equal(df, orig)

    del sys.modules["cx_Oracle"]


@mock.patch(
    "{}.get_user_pw".format(mllp_ds.__name__), return_value=("foo", "bar")
)
def test_oracledatasource_notimplemented(
    user_pw, oracledatasource_cfg_and_data
):
    cfg, dbms_cfg, _ = oracledatasource_cfg_and_data()
    ora_mock = mock.MagicMock()
    sys.modules["cx_Oracle"] = ora_mock

    ds = mllp_ds.OracleDataSource("bla", cfg, dbms_cfg)
    with pytest.raises(NotImplementedError, match="get_dataframe"):
        ds.get_raw()

    del sys.modules["cx_Oracle"]


@pytest.mark.parametrize(
    "values, expected",
    [
        (
            pd.DataFrame(
                {
                    "a": [1, 2, 3, 4, 5, 6, 7],
                    "b": [3, 2, 7, None, 5, 7, 3],
                    "c": [1, 6, np.nan, 5, 7, None, 0],
                }
            ),
            pd.DataFrame(
                {
                    "a": [1, 2, 3, 4, 5, 6, 7],
                    "b": [3, 2, 7, np.nan, 5, 7, 3],
                    "c": [1, 6, np.nan, 5, 7, np.nan, 0],
                }
            ),
        ),
        (
            pd.DataFrame(
                {
                    "a": [1, 2, "3", None, 5, 6, 7],
                    "b": [3, 2, 7, None, "4", 7, 3],
                    "c": [1, 6, np.nan, 5, 7, "0", 0],
                }
            ),
            pd.DataFrame(
                {
                    "a": [1, 2, "3", np.nan, 5, 6, 7],
                    "b": [3, 2, 7, np.nan, "4", 7, 3],
                    "c": [1, 6, np.nan, 5, 7, "0", 0],
                }
            ),
        ),
        (
            pd.DataFrame(
                {
                    "a": [1, 2, "x", 4, 5, 6, 7],
                    "b": [3, 2, 7, None, "y", 7, 3],
                    "c": [1, 6, np.nan, 5, 7, "z", 0],
                }
            ),
            pd.DataFrame(
                {
                    "a": [1, 2, "x", 4, 5, 6, 7],
                    "b": [3, 2, 7, np.nan, "y", 7, 3],
                    "c": [1, 6, np.nan, 5, 7, "z", 0],
                }
            ),
        ),
    ],
)
@mock.patch("pandas.read_sql")
@mock.patch(
    "{}.get_user_pw".format(mllp_ds.__name__), return_value=("foo", "bar")
)
def test_oracledatasource_regression_nas_issue86(
    user_pw, pd_read, values, expected, oracledatasource_cfg_and_data
):
    """
    OracleDataSource should connect, read dataframe and return it unaltered
    with the exception of None values --> they should be converted to np.nan.
    """
    cfg, dbms_cfg, _ = oracledatasource_cfg_and_data()
    ora_mock = mock.MagicMock()
    sys.modules["cx_Oracle"] = ora_mock
    pd_read.return_value = values

    ds = mllp_ds.OracleDataSource("bla", cfg, dbms_cfg)
    df = ds.get_dataframe()

    pd.testing.assert_frame_equal(df, expected)
    # assert df == expected
    ora_mock.connect.assert_called_once()
    pd_read.assert_called_once()

    del sys.modules["cx_Oracle"]


@mock.patch("pandas.DataFrame.to_sql")
@mock.patch(
    "{}.get_user_pw".format(mllp_ds.__name__), return_value=("foo", "bar")
)
def test_oracledatasink_df(user_pw, df_write, oracledatasource_cfg_and_data):
    cfg, dbms_cfg, data = oracledatasource_cfg_and_data()
    del cfg["query"]
    cfg["table"] = "blabla"
    ora_mock = mock.MagicMock()
    sys.modules["cx_Oracle"] = ora_mock
    df_write.return_value = data

    ds = mllp_ds.OracleDataSink("bla", cfg, dbms_cfg)
    ds.put_dataframe(data)

    ora_mock.connect.assert_called_once()
    df_write.assert_called_once()

    del sys.modules["cx_Oracle"]


@mock.patch(
    "{}.get_user_pw".format(mllp_ds.__name__), return_value=("foo", "bar")
)
def test_oracledatasink_notimplemented(user_pw, oracledatasource_cfg_and_data):
    cfg, dbms_cfg, data = oracledatasource_cfg_and_data()
    del cfg["query"]
    cfg["table"] = "blabla"
    ora_mock = mock.MagicMock()
    sys.modules["cx_Oracle"] = ora_mock

    ds = mllp_ds.OracleDataSink("bla", cfg, dbms_cfg)
    with pytest.raises(NotImplementedError):
        ds.put_dataframe(data, chunksize=7)
    with pytest.raises(NotImplementedError, match="put_dataframe"):
        ds.put_raw(data)

    del sys.modules["cx_Oracle"]
