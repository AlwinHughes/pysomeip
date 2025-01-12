
def _unpack(fmt, buf):
    if len(buf) < fmt.size:
        raise IncompleteReadError(
            f"can not parse {fmt.format!r}, got only {len(buf)} bytes"
        )
    return fmt.unpack(buf[: fmt.size]), buf[fmt.size :]


SD_SERVICE = 0xFFFF
SD_METHOD = 0x8100
SD_INTERFACE_VERSION = 1

def _find(haystack, needle):
    """Return the index at which the sequence needle appears in the sequence haystack,
    or -1 if it is not found, using the Boyer-Moore-Horspool algorithm. The elements of
    needle and haystack must be hashable.

    >>> find([1, 1, 2], [1, 2])
    1

    from https://codereview.stackexchange.com/a/19629
    """
    h = len(haystack)
    n = len(needle)
    skip = {needle[i]: n - i - 1 for i in range(n - 1)}
    i = n - 1
    while i < h:
        for j in range(n):
            if haystack[i - j] != needle[-j - 1]:
                i += skip.get(haystack[i], n)
                break
        else:
            return i - n + 1
    return None


class ParseError(RuntimeError):
    pass


class IncompleteReadError(ParseError):
    pass

