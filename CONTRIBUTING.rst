Contributing
============

Would you like to contribute? Great!

Feedback
--------

Please leave feedback, bug reports, and feature requests in the `issue tracker
in GitHub <https://github.com/jasujm/hrefs/issues>`_.

Pull requests
-------------

You are more than welcome to contribute code to the project via `GitHub pull
requests <https://github.com/jasujm/hrefs/pulls>`_.

The project uses `flit <https://pypi.org/project/flit/>`_ for dependency
management.

.. code-block:: console

   $ python -m venv venv
   $ activate venv/bin/activate
   (venv) $ pip install flit
   (venv) $ flit install --symlink --deps=develop

Before creating PR, please make sure that all tests pass by running `tox`:

.. code-block:: console

   (venv) $ tox

For new features you should also update the documentation and ensure it compiles:

.. code-block:: console

   (venv) $ cd docs/
   (venv) $ make html
