"""Machine-readable extract of the contract document (v0.4).

The document is the source of truth. If this file and the document disagree,
the document wins: fix this file and log a contract defect.
"""
DEFAULT_PORT = 18740  # A-002
SCENARIOS = ("no-project", "uml-project", "sysml-project")

STATUS_FIELDS = ("plugin_version", "api_version", "cameo_version", "project_open", "port")  # CL-HSK-001 T2
PROJECT_FIELDS = ("name", "file_path", "root_model_id")                                     # CL-PRJ-001 T2
ELEMENT_FIELDS = ("id", "type", "name", "parent_id", "applied_stereotypes")                 # CL-ELM-001 7.2
REQUEST_FIELDS = ("type", "name", "parent_id", "metaclasses")                               # CL-ELM-001 7.2

# CL-ELM-001 7.2.1 (39 tokens, case-sensitive)
SUPPORTED_TYPES = (
    "Package", "Profile", "Stereotype", "Class", "Block", "Property", "FlowProperty", "Port",
    "Interface", "Activity", "UseCase", "Actor", "StateMachine", "State", "Pseudostate",
    "InitialState", "Requirement", "InterfaceBlock", "ConstraintBlock", "ValueType", "DataType",
    "Signal", "Enumeration", "Component", "Comment", "Constraint", "CallBehaviorAction",
    "OpaqueAction", "ActivityPartition", "InitialNode", "ActivityFinalNode", "FlowFinalNode",
    "DecisionNode", "MergeNode", "ForkNode", "JoinNode", "InputPin", "OutputPin", "Operation",
)
# The SysML aliases the reference names; the complete set is OPEN in the contract.
SYSML_TYPES = ("Block", "Requirement", "ConstraintBlock", "InterfaceBlock", "ValueType", "FlowProperty")

# CL-ELM-001 B4 and D-012: aliases a create response and every read report under their canonical token.
CANONICAL_TYPE = {"InitialState": "Pseudostate"}
ROOT_TYPE = "Model"  # CL-ELM-002 B5: the root model is reported as type "Model" with parent_id null

API_VERSION = 1             # CL-HSK-002
MIN_CLIENT_API_VERSION = 1  # CL-HSK-002
CAPABILITIES_FIELDS = ("plugin_version", "api_version", "min_client_api_version", "routes", "element_types")
# CL-HSK-002 B4: exactly the routes of api_version 1. Order is not significant.
ROUTES_V1 = (
    ("GET", "/api/v1/status"),
    ("GET", "/api/v1/capabilities"),
    ("GET", "/api/v1/project"),
    ("POST", "/api/v1/elements"),
    ("GET", "/api/v1/elements/{id}"),
    ("POST", "/api/v1/elements/query"),
    ("POST", "/api/v1/elements/{id}/delete"),
)

QUERY_FIELDS = ("parent_id", "type", "name", "stereotype", "limit", "cursor")  # CL-ELM-002
QUERY_LIMIT_DEFAULT = 100
QUERY_LIMIT_MAX = 500
DELETE_FIELDS = ("allow_write",)  # CL-ELM-003
PREVIEW_LIMIT = 500               # CL-ELM-003 B7

# Raised by the Python MCP server, never by the plugin (G-012).
SERVER_ERRORS = ("PLUGIN_INCOMPATIBLE", "PLUGIN_UNREACHABLE", "PLUGIN_OUT_OF_SYNC")

# G-002, G-012
ERROR_STATUS = {
    "INVALID_REQUEST": 400,
    "UNSUPPORTED_TYPE": 400,
    "PARENT_NOT_FOUND": 404,
    "ELEMENT_NOT_FOUND": 404,
    "ROUTE_NOT_FOUND": 404,
    "METHOD_NOT_ALLOWED": 405,
    "NO_ACTIVE_PROJECT": 409,
    "SESSION_CONFLICT": 409,
    "REQUIRED_PROFILE_MISSING": 422,
    "INVALID_PARENT_FOR_TYPE": 422,
    "PROTECTED_ELEMENT": 422,
    "ELEMENT_READ_ONLY": 422,
    "INTERNAL_ERROR": 500,
    "TIMEOUT": 504,
}
