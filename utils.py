from datetime import datetime, time


def in_between(now, start, end):
    """A function to check if a time is in between two other times

    Arguments
    ---------
    now: time
        the time to check
    start: time
        the start time
    end: time
        the end time

    Example usage
    -------------
    >>> in_between(datetime.now().time(), datetime(2021, 5, 20, 0, 0, 0).time(), datetime(2021, 5, 20, 23, 59, 59).time())
    """
    if start < end:
        return start <= now < end
    elif start == end:
        return True
    else:  # over midnight e.g., 23:30-04:15
        return start <= now or now < end
