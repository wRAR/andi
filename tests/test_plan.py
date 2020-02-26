from typing import Union, Optional

import pytest

import andi
from andi import plan_str, FunctionArguments


class A:

    def __init__(self, e: 'E'):
        pass


class B:
    pass


class C:

    def __init__(self, a: A, b: B):
        pass


class D:

    def __init__(self, a: A, c: C):
        pass


class E:

    def __init__(self, b: B, c: C, d: D):
        pass


ALL = [A, B, C, D, E]
SOME = [A, B, C]

def test_plan_and_build():
    plan = andi.plan_for_class(E, lambda x: True, [A])

    assert set(list(plan.keys())[:2]) == {A, B}
    assert list(plan.values())[:2] == [{}, {}]
    assert list(plan.items())[2:] == [
        (C, {'a': A, 'b': B}),
        (D, {'a': A, 'c': C}),
        (E, {'b': B, 'c': C, 'd': D})
    ]
    instances = andi.build(plan, {A: ""})
    assert type(instances[E]) == E


def test_cyclic_dependency():
    andi.plan_for_class(E, lambda x: True, [A])  # No error if externally provided
    with pytest.raises(andi.CyclicDependencyError):
        andi.plan_for_class(E, lambda x: True, [])


@pytest.mark.parametrize("cls,can_provide,externally_provided", [
    (E, ALL, SOME),
    (C, SOME, ALL),
    (E, ALL, ALL)
])
def test_plan_container_or_func(cls, can_provide, externally_provided):
    plan_func = andi.plan_for_class(cls, can_provide.__contains__,
                          externally_provided.__contains__)
    plan_container = andi.plan_for_class(cls, can_provide, externally_provided)
    assert plan_func == plan_container


def test_cannot_be_provided():
    class WithB:

        def __init__(self, b: B):
            pass

    plan = list(andi.plan_for_class(WithB, [WithB, B], [B]).items())
    assert plan == [(B, {}), (WithB, {"b": B})]
    with pytest.raises(andi.NonProvidableError):
        andi.plan_for_class(WithB, [WithB], [])
    with pytest.raises(andi.NonProvidableError):
        andi.plan_for_class(WithB, [], [])

    class WithOptionals:

        def __init__(self, a_or_b: Union[A, B]):
            pass

    plan = list(andi.plan_for_class(WithOptionals, [WithOptionals, A, B], [A]).items())
    assert plan == [(A, {}), (WithOptionals, {'a_or_b': A})]

    plan = list(andi.plan_for_class(WithOptionals, [WithOptionals, B], [A]).items())
    assert plan == [(B, {}), (WithOptionals, {'a_or_b': B})]

    with pytest.raises(andi.NonProvidableError):
        andi.plan_for_class(WithOptionals, [WithOptionals], [A]).items()


def test_externally_provided():
    plan = andi.plan_for_class(E, ALL, ALL)
    assert plan == {E: {}}

    plan = andi.plan_for_class(E, ALL, [A, B, C, D])
    assert plan.keys() == {B, C, D, E}
    assert list(plan.keys())[-1] == E
    assert plan[E] == {'b': B, 'c': C, 'd': D}

    plan = andi.plan_for_class(E, ALL, [A, B, D])
    seq = list(plan.keys())
    assert seq.index(A) < seq.index(C)
    assert seq.index(B) < seq.index(C)
    assert seq.index(D) < seq.index(E)
    assert seq.index(C) < seq.index(E)
    for cls in (A, B, D):
        assert plan[cls] == {}
    assert plan[C] == {'a': A, 'b': B}
    assert plan[E] == {'b': B, 'c': C, 'd': D}


def test_plan_for_func():
    def fn(other: str, e: E, c: C):
        assert other == 'yeah!'
        assert type(e) == E
        assert type(c) == C

    plan = andi.plan_for_func(fn, ALL, [A])
    assert list(plan.items())[-1] == (FunctionArguments, {'e': E, 'c': C})
    instances = andi.build(plan, {A: ""})
    kwargs = dict(other="yeah!", e=instances[E], c=instances[C])
    fn(**kwargs)


def test_plan_with_optionals():
    def fn(a: Optional[str]):
        pass

    assert andi.plan_for_func(fn, [type(None), str], [str]) == \
           {str: {}, FunctionArguments: {'a': str}}
    plan = andi.plan_for_func(fn, [type(None)], [])
    assert plan == {type(None): {}, FunctionArguments: {'a': type(None)}}
    assert andi.build(plan)[type(None)] == None


def test_plan_class_non_annotated():
    class WithNonAnnArgs:

        def __init__(self, a: A, b: B, non_ann, non_ann_def=0, *,
                     non_ann_kw, non_ann_kw_def=1):
            pass

    plan = andi.plan_for_func(WithNonAnnArgs.__init__, ALL + [WithNonAnnArgs], [A])
    assert plan == {A: {}, B: {}, FunctionArguments: {'a': A, 'b': B}}

    with pytest.raises(andi.NonProvidableError):
        andi.plan_for_class(WithNonAnnArgs, ALL + [WithNonAnnArgs], [A])
