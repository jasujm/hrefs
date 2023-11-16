"""The library exception hierarchy"""


class ReferrableModelError(Exception):
    """An exception indicating error in a referrable model

    This exception is raised whenever the library detects an incorrectly
    configured or otherwise invalid model.  It typically indicates an error in
    the code and not the input.
    """
