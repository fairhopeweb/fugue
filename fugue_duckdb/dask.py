from typing import Any, Optional, Union

import dask.dataframe as dd
import duckdb
import pyarrow as pa
from dask.distributed import Client
from duckdb import DuckDBPyConnection
from triad import assert_or_throw

from fugue import DataFrame, MapEngine, PartitionSpec
from fugue.collections.partition import EMPTY_PARTITION_SPEC
from fugue_dask import DaskDataFrame, DaskExecutionEngine
from fugue_dask.execution_engine import DaskMapEngine
from fugue_duckdb.dataframe import DuckDataFrame
from fugue_duckdb.execution_engine import DuckExecutionEngine


class DuckDaskExecutionEngine(DuckExecutionEngine):
    """A hybrid engine of DuckDB and Dask. Most operations will be done by
    DuckDB, but for ``map``, it will use Dask to fully utilize local CPUs.
    The engine can be used with a real Dask cluster, but practically, this
    is more useful for local process.

    :param conf: |ParamsLikeObject|, read |FugueConfig| to learn Fugue specific options
    :param connection: DuckDB connection
    """

    def __init__(
        self,
        conf: Any = None,
        connection: Optional[DuckDBPyConnection] = None,
        dask_client: Optional[Client] = None,
    ):
        super().__init__(conf, connection)
        self._dask_engine = DaskExecutionEngine(dask_client=dask_client, conf=conf)

    def create_default_map_engine(self) -> MapEngine:
        return DaskMapEngine(self._dask_engine)

    @property
    def dask_client(self) -> Client:
        return self._dask_engine.dask_client

    def to_df(self, df: Any, schema: Any = None) -> DuckDataFrame:
        if isinstance(df, (dd.DataFrame, DaskDataFrame)):
            ddf = self._to_dask_df(df, schema)
            if all(not pa.types.is_nested(f.type) for f in ddf.schema.fields):
                return DuckDataFrame(self.connection.df(ddf.as_pandas()))
            else:
                return DuckDataFrame(
                    duckdb.arrow(ddf.as_arrow(), connection=self.connection)
                )
        return super().to_df(df, schema)

    def repartition(self, df: DataFrame, partition_spec: PartitionSpec) -> DataFrame:
        tdf = self._to_auto_df(df)
        if isinstance(tdf, DaskDataFrame):
            return self._dask_engine.repartition(tdf, partition_spec=partition_spec)
        return super().repartition(tdf, partition_spec=partition_spec)

    def broadcast(self, df: DataFrame) -> DataFrame:
        if isinstance(df, DaskDataFrame):
            return self._dask_engine.broadcast(df)
        return super().broadcast(df)

    def persist(
        self,
        df: DataFrame,
        lazy: bool = False,
        **kwargs: Any,
    ) -> DataFrame:
        if isinstance(df, DaskDataFrame):
            return self._dask_engine.persist(df, lazy=lazy, **kwargs)
        return super().persist(df, lazy=lazy, **kwargs)

    def save_df(
        self,
        df: DataFrame,
        path: str,
        format_hint: Any = None,
        mode: str = "overwrite",
        partition_spec: PartitionSpec = EMPTY_PARTITION_SPEC,
        force_single: bool = False,
        **kwargs: Any,
    ) -> None:
        if isinstance(df, DaskDataFrame) or not partition_spec.empty:
            return self._dask_engine.save_df(
                self._to_dask_df(df),
                path=path,
                format_hint=format_hint,
                mode=mode,
                partition_spec=partition_spec,
                force_single=force_single,
                **kwargs,
            )
        return super().save_df(
            df,
            path=path,
            format_hint=format_hint,
            mode=mode,
            partition_spec=partition_spec,
            force_single=force_single,
            **kwargs,
        )

    def convert_yield_dataframe(self, df: DataFrame, as_local: bool) -> DataFrame:
        if isinstance(df, DaskDataFrame):
            return self._dask_engine.convert_yield_dataframe(df, as_local)
        return super().convert_yield_dataframe(df, as_local)

    def _to_auto_df(
        self, df: Any, schema: Any = None
    ) -> Union[DuckDataFrame, DaskDataFrame]:
        if isinstance(df, (DuckDataFrame, DaskDataFrame)):
            assert_or_throw(
                schema is None,
                ValueError("schema must be None when df is a DataFrame"),
            )
            return df
        if isinstance(df, dd.DataFrame):
            return self._dask_engine.to_df(df, schema)
        return self._to_duck_df(df, schema)

    def _to_dask_df(self, df: Any, schema: Any = None) -> DaskDataFrame:
        if isinstance(df, DuckDataFrame):
            return self._dask_engine.to_df(df.as_pandas(), df.schema)
        return self._dask_engine.to_df(df, schema)
