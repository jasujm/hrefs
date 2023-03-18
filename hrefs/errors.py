"""The library exception hierarchy"""


class ReferrableModelError(Exception):
    """An exception indicating error in a referrable model

    This exception is raised whenever the library detects an incorrectly
    configured or otherwise invalid model.  It is an error condition requiring
    changes to the code rather than an error in the input.
    """
