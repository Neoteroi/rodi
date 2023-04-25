def class_name(input_type):
    generic_alias = "<class 'types.GenericAlias'>"
    if input_type in {list, set} and str(type(input_type)) == generic_alias:
        # for Python 3.9 list[T], set[T]
        return str(input_type)
    try:
        return input_type.__name__
    except AttributeError:
        # for example, this is the case for List[str], Tuple[str, ...], etc.
        return str(input_type)
