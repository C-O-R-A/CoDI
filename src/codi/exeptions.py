class ProtocolError(Exception):
    """Base class for protocol errors"""


class ProtocolSchemaError(ProtocolError):
    """Missing keys or wrong types"""


class ProtocolSemanticError(ProtocolError):
    """Invalid values, shapes, ranges"""
