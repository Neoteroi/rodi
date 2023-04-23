import re

first_cap_re = re.compile("(.)([A-Z][a-z]+)")
all_cap_re = re.compile("([a-z0-9])([A-Z])")


def to_standard_param_name(name):
    value = all_cap_re.sub(r"\1_\2", first_cap_re.sub(r"\1_\2", name)).lower()
    if value.startswith("i_"):
        return "i" + value[2:]
    return value
