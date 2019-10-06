wadze - WebAssembly Decoder - Zero Extras
==========================================

Wadze is a library that parses WebAssembly .wasm binary files into a
Python dictionary that holds the contents of the associated
WebAssembly module.  It does nothing more and has no dependencies.
However, it is quite small, fast, can run in parallel, and could
be used to build other tools that might want to manipulate WebAssembly
in some way.

Usage
-----

Here is an example showing how to use it:

.. code:: python

    import wadze

    with open('input.wasm', 'rb') as file:
        data = file.read()

    module = wadze.parse_module(data)
    
    # If you also want function code decoded into instructions, do this
    module['code'] = [ wadze.parse_code(c) for c in module['code']]

In this example, the resulting ``module`` is a dictionary containing
the contents of the different sections of a Wasm module.  For example,
to see the exported objects, do this:

.. code:: python

    for exp in module['export']:
        print(exp)

The data representation stays fairly faithful to how WebAssembly
encodes modules, but wadze tries to make it a touch more "Pythonic."
The final data structure is a dictionary that mostly contains a mix of
lists and named tuples.

Decoding of instructions can be done in parallel using multiprocessing.
For example:

.. code:: python
    
    import multiprocessing
    pool = multiprocessing.Pool()
    module['code'] = pool.map(wadze.parse_code, module['code'], 100)

In informal tests on the author's machine, Wadze is able to fully
decode a Wasm file containing more than 25000 functions in under 15
seconds using a single CPU core.  It's even faster with multiprocessing.

Questions and Answers
---------------------

**Q: What's this library for?**

A: The primary purpose of this library is to have a simple and
efficient Wasm decoder that might be useful for building other Python
tools that want to manipulate WebAssembly in some way.  It might also
serve an educational purpose in illustrating how WebAssembly can be
easily decoded using a simple recursive descent parser.

**Q: How do I install it?**

A: Wadze consists of a single Python file ``wadze.py``.  Copy it into your project.

**Q: Can I contribute?**

A: Bug reports are welcome, but what you see here is what it is.  Wadze
is not the start of a proto-framework or an effort to make something larger.
Smaller is better.

About
-----
Wadze is a creation of David Beazley (@dabeaz).  https://www.dabeaz.com

P.S.
----
You should come take a `course <https://www.dabeaz.com/courses.html>`_!



