from typing import Any, Dict, Iterable, List

import pandas as pd
from fugue.dataframe import ArrayDataFrame
from fugue.exceptions import FugueInterfacelessError
from fugue.extensions.transformer import (
    Transformer,
    _to_transformer,
    parse_transformer,
    register_transformer,
    transformer,
)
from pytest import raises
from triad import ParamDict, to_uuid
from triad.collections.schema import Schema


def test_transformer():
    assert isinstance(t1, Transformer)
    df = ArrayDataFrame([[0]], "a:int")
    t1._output_schema = t1.get_output_schema(df)
    assert t1.output_schema == "a:int,b:int"
    t2._output_schema = t2.get_output_schema(df)
    assert t2.output_schema == "b:int,a:int"
    t3._output_schema = t3.get_output_schema(df)
    assert t3.output_schema == "a:int,b:int"
    assert [[0, 1]] == list(t3(df.as_array_iterable()))


def test__to_transformer():
    a = _to_transformer(MockTransformer)
    assert isinstance(a, MockTransformer)
    b = _to_transformer("MockTransformer")
    assert isinstance(b, MockTransformer)

    a = _to_transformer(t1, None)
    assert isinstance(a, Transformer)
    a._x = 1
    # every parse should produce a different transformer even the input is
    # a transformer instance
    b = _to_transformer(t1, None)
    assert isinstance(b, Transformer)
    assert "_x" not in b.__dict__
    c = _to_transformer("t1", None)
    assert isinstance(c, Transformer)
    assert "_x" not in c.__dict__
    c._x = 1
    d = _to_transformer("t1", None)
    assert isinstance(d, Transformer)
    assert "_x" not in d.__dict__
    raises(FugueInterfacelessError, lambda: _to_transformer(t4, None))
    raises(FugueInterfacelessError, lambda: _to_transformer("t4", None))
    e = _to_transformer("t4", "*,b:int")
    assert isinstance(e, Transformer)
    f = _to_transformer("t5")
    assert isinstance(f, Transformer)
    g = _to_transformer("t6", "*,b:int")
    assert isinstance(g, Transformer)
    h = _to_transformer("t7")
    assert isinstance(h, Transformer)
    i = _to_transformer("t8")
    assert isinstance(i, Transformer)
    j = _to_transformer("t9")
    assert isinstance(j, Transformer)
    k = _to_transformer("t10")
    assert isinstance(k, Transformer)


def test__register():
    register_transformer("t_x", MockTransformer)
    b = _to_transformer("t_x")
    assert isinstance(b, MockTransformer)

    register_transformer("t_t3", t3)
    register_transformer("t_t4", t4)
    register_transformer("t_t5", t5)
    assert isinstance(_to_transformer("t_t3"), Transformer)
    assert isinstance(_to_transformer("t_t4", "*,x:int"), Transformer)
    assert isinstance(_to_transformer("t_t5"), Transformer)

    # schema: *
    def register_temp(df: pd.DataFrame) -> pd.DataFrame:
        return df

    t = _to_transformer("register_temp")
    assert isinstance(t, Transformer)
    assert not isinstance(t, MockTransformer)
    # registered alias has the highest priority
    register_transformer("register_temp", MockTransformer)
    t = _to_transformer("register_temp")
    assert isinstance(t, MockTransformer)

    # can't overwrite
    raises(
        KeyError,
        lambda: register_transformer(
            "register_temp", MockTransformer, on_dup=ParamDict.THROW
        ),
    )


def test__to_transformer_determinism():
    a = _to_transformer(t1, None)
    b = _to_transformer(t1, None)
    c = _to_transformer("t1", None)
    assert a is not b
    assert to_uuid(a) == to_uuid(b)
    assert a is not c
    assert to_uuid(a) == to_uuid(c)

    a = _to_transformer(t4, "*,b:int")
    b = _to_transformer("t4", "*,b:int")
    assert a is not b
    assert to_uuid(a) == to_uuid(b)

    a = _to_transformer(t4, "a:int,b:int")
    b = _to_transformer("t4", Schema("a:int,b:int"))
    assert a is not b
    assert to_uuid(a) == to_uuid(b)

    a = _to_transformer(MockTransformer)
    b = _to_transformer("MockTransformer")
    assert a is not b
    assert to_uuid(a) == to_uuid(b)

    a = _to_transformer(t10)
    b = _to_transformer("t10")
    assert a is not b
    assert to_uuid(a) == to_uuid(b)


def test_to_transformer_validation():
    @transformer(["*", None, "b:int"], input_has=" a , b ")
    def tv1(df: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
        for r in df:
            r["b"] = 1
            yield r

    # input_has: a , b
    # schema: *,b:int
    def tv2(df: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
        for r in df:
            r["b"] = 1
            yield r

    class MockTransformerV(Transformer):
        @property
        def validation_rules(self):
            return {"input_is": "a:int,b:int"}

        def get_output_schema(self, df):
            pass

        def transform(self, df):
            pass

    a = _to_transformer(tv1, None)
    assert {"input_has": ["a", "b"]} == a.validation_rules
    b = _to_transformer(tv2, None)
    assert {"input_has": ["a", "b"]} == b.validation_rules
    c = _to_transformer(MockTransformerV)
    assert {"input_is": "a:int,b:int"} == c.validation_rules


def test_inside_class():
    class Test(object):
        # schema: *
        # input_is: a:int , b :int
        def t1(self, df: pd.DataFrame) -> pd.DataFrame:
            return df

    test = Test()
    a = _to_transformer(test.t1)
    assert isinstance(a, Transformer)
    assert {"input_is": "a:int,b:int"} == a.validation_rules


def test_parse_transformer():
    @parse_transformer.candidate(lambda x: isinstance(x, str) and x.startswith("(("))
    def _parse(obj):
        return MockTransformer(obj)

    a = _to_transformer("((abc")
    b = _to_transformer("((bc")
    c = _to_transformer("((abc")

    assert isinstance(a, MockTransformer)
    assert isinstance(b, MockTransformer)
    assert isinstance(c, MockTransformer)
    assert to_uuid(a) == to_uuid(c)
    assert to_uuid(a) != to_uuid(b)


@transformer(["*", None, "b:int"])
def t1(df: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for r in df:
        r["b"] = 1
        yield r


@transformer([Schema("b:int"), "*"])
def t2(df: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for r in df:
        r["b"] = 1
        yield r


@transformer(Schema("a:int, b:int"))
def t3(df: Iterable[List[Any]]) -> Iterable[List[Any]]:
    for r in df:
        r += [1]
        yield r


def t4(df: Iterable[List[Any]]) -> Iterable[List[Any]]:
    for r in df:
        r += [1]
        yield r


# schema: *,b:int
def t5(df: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for r in df:
        r["b"] = 1
        yield r


def t6(df: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for r in df:
        r["b"] = 1
        yield r


# schema: *
def t7(df: pd.DataFrame) -> Iterable[pd.DataFrame]:
    yield df


# schema: *
def t8(df: Iterable[pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(list(df))


# schema: *
def t9(df: pd.DataFrame) -> Iterable[pd.DataFrame]:
    yield df


# schema: *
def t10(df: pd.DataFrame, c: callable) -> pd.DataFrame:
    yield df


class MockTransformer(Transformer):
    def __init__(self, x=""):
        self._x = x

    def get_output_schema(self, df):
        pass

    def transform(self, df):
        pass

    def __uuid__(self) -> str:
        return to_uuid(super().__uuid__(), self._x)
