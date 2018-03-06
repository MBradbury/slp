
try:
    import lazy_import
    lazy_import.lazy_module("pandas")
    lazy_import.lazy_module("base64")
    lazy_import.lazy_module("re")
    lazy_import.lazy_module("pickle")
except ImportError:
    pass
